import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/simple.dart';

class VideoPlayerView extends StatefulWidget {
  final String path;

  const VideoPlayerView({super.key, required this.path});

  @override
  State<VideoPlayerView> createState() => _VideoPlayerViewState();
}

class _VideoPlayerViewState extends State<VideoPlayerView> {
  Stream<ui.Image>? _videoStream;

  void _startStreaming() {
    setState(() {
      _videoStream = streamVideo(path: widget.path).asyncMap((frame) async {
        try {
          // RGBA 데이터 크기가 예상과 맞는지 확인 (디버깅용)
          // debugPrint('Frame: ${frame.width}x${frame.height}, Pixels: ${frame.pixels.length}');

          final buffer = await ui.ImmutableBuffer.fromUint8List(frame.pixels);
          final descriptor = ui.ImageDescriptor.raw(
            buffer,
            width: frame.width,
            height: frame.height,
            pixelFormat: ui.PixelFormat.rgba8888,
          );
          final codec = await descriptor.instantiateCodec();
          final frameInfo = await codec.getNextFrame();
          return frameInfo.image;
        } catch (e) {
          debugPrint('Frame conversion error: $e');
          rethrow;
        }
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<ui.Image>(
      stream: _videoStream,
      builder: (context, snapshot) {
        if (snapshot.hasData) {
          return Container(
            constraints: const BoxConstraints(maxHeight: 400),
            decoration: BoxDecoration(
              border: Border.all(color: Colors.blue, width: 2),
              borderRadius: BorderRadius.circular(8),
            ),
            clipBehavior: Clip.antiAlias,
            child: RawImage(image: snapshot.data!, fit: BoxFit.contain),
          );
        }

        if (snapshot.hasError) {
          return Column(
            children: [
              const Icon(Icons.error_outline, color: Colors.red, size: 40),
              const SizedBox(height: 10),
              Text('재생 오류: ${snapshot.error}', textAlign: TextAlign.center),
            ],
          );
        }

        if (_videoStream != null) {
          return const Column(
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 10),
              Text('스트리밍 대기 중...'),
            ],
          );
        }

        return ElevatedButton.icon(
          onPressed: _startStreaming,
          icon: const Icon(Icons.play_arrow),
          label: const Text('앱 내에서 재생 시작'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.blue,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          ),
        );
      },
    );
  }
}
