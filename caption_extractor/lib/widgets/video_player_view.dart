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
  ui.Image? _thumbnail;
  bool _isLoadingThumbnail = false;

  @override
  void initState() {
    super.initState();
    _loadThumbnail();
  }

  @override
  void didUpdateWidget(VideoPlayerView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.path != widget.path) {
      setState(() {
        _videoStream = null;
        _thumbnail = null;
      });
      _loadThumbnail();
    }
  }

  Future<void> _loadThumbnail() async {
    setState(() {
      _isLoadingThumbnail = true;
    });

    try {
      final frame = await getFirstFrame(path: widget.path);
      final buffer = await ui.ImmutableBuffer.fromUint8List(frame.pixels);
      final descriptor = ui.ImageDescriptor.raw(
        buffer,
        width: frame.width,
        height: frame.height,
        pixelFormat: ui.PixelFormat.rgba8888,
      );
      final codec = await descriptor.instantiateCodec();
      final frameInfo = await codec.getNextFrame();

      if (mounted) {
        setState(() {
          _thumbnail = frameInfo.image;
          _isLoadingThumbnail = false;
        });
      }
    } catch (e) {
      debugPrint('Thumbnail loading error: $e');
      if (mounted) {
        setState(() {
          _isLoadingThumbnail = false;
        });
      }
    }
  }

  void _startStreaming() {
    setState(() {
      _videoStream = streamVideo(path: widget.path).asyncMap((frame) async {
        try {
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
    return Column(
      children: [
        if (_videoStream != null)
          StreamBuilder<ui.Image>(
            stream: _videoStream,
            builder: (context, snapshot) {
              if (snapshot.hasData) {
                return _buildVideoContainer(
                  RawImage(image: snapshot.data!, fit: BoxFit.contain),
                );
              }

              if (snapshot.hasError) {
                return _buildErrorWidget(snapshot.error.toString());
              }

              return _buildLoadingWidget('스트리밍 대기 중...');
            },
          )
        else if (_thumbnail != null)
          GestureDetector(
            onTap: _startStreaming,
            child: Stack(
              alignment: Alignment.center,
              children: [
                _buildVideoContainer(
                  RawImage(image: _thumbnail!, fit: BoxFit.contain),
                ),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: const BoxDecoration(
                    color: Colors.black45,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.play_arrow,
                    size: 48,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          )
        else if (_isLoadingThumbnail)
          _buildLoadingWidget('썸네일 로드 중...')
        else
          _buildErrorWidget('비디오를 로드할 수 없습니다.'),
      ],
    );
  }

  Widget _buildVideoContainer(Widget child) {
    return Container(
      constraints: const BoxConstraints(maxHeight: 400),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.blue.withOpacity(0.5), width: 2),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.2),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: child,
    );
  }

  Widget _buildLoadingWidget(String message) {
    return Container(
      height: 200,
      alignment: Alignment.center,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(message),
        ],
      ),
    );
  }

  Widget _buildErrorWidget(String error) {
    return Container(
      height: 200,
      alignment: Alignment.center,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, color: Colors.red, size: 40),
          const SizedBox(height: 10),
          Text('오류: $error', textAlign: TextAlign.center),
        ],
      ),
    );
  }
}
