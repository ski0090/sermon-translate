import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/simple.dart';
import 'package:caption_extractor/src/rust/frb_generated.dart';

import 'package:file_picker/file_picker.dart';

Future<void> main() async {
  await RustLib.init();
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  String? selectedPath;
  VideoInfo? videoInfo;
  Stream<ui.Image>? videoStream;
  bool isLoading = false;

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['mp4', 'mkv', 'avi'],
    );

    if (result != null && result.files.single.path != null) {
      final path = result.files.single.path!;
      setState(() {
        selectedPath = path;
        isLoading = true;
        videoInfo = null;
        videoStream = null;
      });

      try {
        final info = await getVideoInfo(path: path);
        setState(() {
          videoInfo = info;
          isLoading = false;
        });
      } catch (e) {
        debugPrint('Error getting video info: $e');
        setState(() {
          isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final fileName = selectedPath != null
        ? selectedPath!.split(RegExp(r'[/\\]')).last
        : null;

    return MaterialApp(
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blue),
      home: Scaffold(
        appBar: AppBar(
          title: const Text('Caption Extractor'),
          actions: [
            IconButton(
              onPressed: _pickFile,
              icon: const Icon(Icons.video_file_outlined),
              tooltip: '영상 파일 선택',
            ),
          ],
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (isLoading)
                const CircularProgressIndicator()
              else if (videoInfo != null) ...[
                Card(
                  margin: const EdgeInsets.symmetric(horizontal: 20),
                  elevation: 4,
                  child: Padding(
                    padding: const EdgeInsets.all(20.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.movie_outlined,
                              color: Colors.blue,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                fileName ?? '',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 18,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                        const Divider(height: 10),
                        _infoItem(
                          Icons.aspect_ratio,
                          '해상도',
                          '${videoInfo!.width} x ${videoInfo!.height}',
                        ),
                        _infoItem(
                          Icons.timer_outlined,
                          '재생 시간',
                          '${(videoInfo!.durationMs.toDouble() / 1000).toStringAsFixed(2)} 초',
                        ),
                        _infoItem(
                          Icons.slow_motion_video,
                          '프레임 레이트',
                          '${videoInfo!.fps.toStringAsFixed(2)} fps',
                        ),
                        _infoItem(Icons.code, '포맷', videoInfo!.format),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                StreamBuilder<ui.Image>(
                  stream: videoStream,
                  builder: (context, snapshot) {
                    if (snapshot.hasData) {
                      final image = snapshot.data!;
                      return Container(
                        constraints: const BoxConstraints(maxHeight: 300),
                        decoration: BoxDecoration(
                          border: Border.all(color: Colors.blue, width: 2),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        clipBehavior: Clip.antiAlias,
                        child: RawImage(image: image, fit: BoxFit.contain),
                      );
                    }
                    if (videoStream != null) {
                      return const Column(
                        children: [
                          CircularProgressIndicator(),
                          SizedBox(height: 10),
                          Text('스트리밍 대기 중...'),
                        ],
                      );
                    }
                    return ElevatedButton.icon(
                      onPressed: () {
                        setState(() {
                          videoStream = streamVideo(path: selectedPath!)
                              .asyncMap((frame) async {
                                final buffer =
                                    await ui.ImmutableBuffer.fromUint8List(
                                      frame.pixels,
                                    );
                                final descriptor = ui.ImageDescriptor.raw(
                                  buffer,
                                  width: frame.width,
                                  height: frame.height,
                                  pixelFormat: ui.PixelFormat.rgba8888,
                                );
                                final codec = await descriptor
                                    .instantiateCodec();
                                final frameInfo = await codec.getNextFrame();
                                return frameInfo.image;
                              });
                        });
                      },
                      icon: const Icon(Icons.play_arrow),
                      label: const Text('앱 내에서 재생 시작'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blue,
                        foregroundColor: Colors.white,
                      ),
                    );
                  },
                ),
              ] else
                Column(
                  children: [
                    const Icon(
                      Icons.video_collection_outlined,
                      size: 60,
                      color: Colors.grey,
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      '파일을 선택해 주세요',
                      style: TextStyle(color: Colors.grey),
                    ),
                    const SizedBox(height: 20),
                    Text(
                      'GStreamer: ${getGstreamerVersion()}',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _infoItem(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 18, color: Colors.grey[600]),
          const SizedBox(width: 10),
          Text('$label: ', style: TextStyle(color: Colors.grey[700])),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }
}
