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
    return MaterialApp(
      home: Scaffold(
        appBar: AppBar(title: const Text('Caption Extractor')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('GStreamer: ${getGstreamerVersion()}'),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: _pickFile,
                child: const Text('영상 파일 선택'),
              ),
              if (isLoading)
                const Padding(
                  padding: EdgeInsets.all(20.0),
                  child: CircularProgressIndicator(),
                ),
              if (selectedPath != null && !isLoading) ...[
                const SizedBox(height: 20),
                Text('파일 경로: $selectedPath', textAlign: TextAlign.center),
                if (videoInfo != null) ...[
                  const SizedBox(height: 20),
                  Card(
                    margin: const EdgeInsets.symmetric(horizontal: 20),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            '영상 정보',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 18,
                            ),
                          ),
                          const Divider(),
                          Text(
                            '해상도: ${videoInfo!.width} x ${videoInfo!.height}',
                          ),
                          Text(
                            '재생 시간: ${(videoInfo!.durationMs.toDouble() / 1000).toStringAsFixed(2)} 초',
                          ),
                          Text(
                            '프레임 레이트: ${videoInfo!.fps.toStringAsFixed(2)} fps',
                          ),
                          Text(
                            '포맷: ${videoInfo!.format}',
                            overflow: TextOverflow.ellipsis,
                            maxLines: 2,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}
