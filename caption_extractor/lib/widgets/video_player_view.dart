import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/simple.dart';
import 'roi_selector.dart';

class VideoPlayerView extends StatefulWidget {
  final String path;
  final VideoInfo videoInfo;

  const VideoPlayerView({
    super.key,
    required this.path,
    required this.videoInfo,
  });

  @override
  State<VideoPlayerView> createState() => _VideoPlayerViewState();
}

class _VideoPlayerViewState extends State<VideoPlayerView> {
  Stream<ui.Image>? _videoStream;
  ui.Image? _thumbnail;
  bool _isLoadingThumbnail = false;
  Rect? _selectedRect;
  bool _isRoiMode = false;

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
        _selectedRect = null;
        _isRoiMode = false;
      });
      _loadThumbnail();
    }
  }

  Future<void> _loadThumbnail({Roi? roi}) async {
    setState(() {
      _isLoadingThumbnail = true;
    });

    try {
      final frame = await getFirstFrame(path: widget.path, roi: roi);
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

  void _startStreaming({Roi? roi}) {
    setState(() {
      _videoStream = streamVideo(path: widget.path, roi: roi).asyncMap((
        frame,
      ) async {
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

  void _applyRoi() {
    if (_videoStream != null) {
      // 스트리밍 중이면 중지 후 새 ROI로 재시작
      setState(() {
        _videoStream = null;
      });
    }
    // 썸네일 갱신
    _loadThumbnail(roi: _convertRectToRoi(_selectedRect, _lastWidgetSize));
  }

  Size _lastWidgetSize = Size.zero;

  Roi? _convertRectToRoi(Rect? rect, Size widgetSize) {
    if (rect == null || widgetSize == Size.zero) return null;

    final vWidth = widget.videoInfo.width;
    final vHeight = widget.videoInfo.height;

    final scaleX = vWidth / widgetSize.width;
    final scaleY = vHeight / widgetSize.height;

    return Roi(
      x: (rect.left * scaleX).toInt(),
      y: (rect.top * scaleY).toInt(),
      width: (rect.width * scaleX).toInt(),
      height: (rect.height * scaleY).toInt(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildVideoArea(),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton.icon(
              onPressed: () {
                setState(() {
                  _isRoiMode = !_isRoiMode;
                  if (!_isRoiMode) {
                    _applyRoi();
                  }
                });
              },
              icon: Icon(_isRoiMode ? Icons.check : Icons.crop),
              label: Text(_isRoiMode ? '선택 완료' : '영역 선택'),
              style: ElevatedButton.styleFrom(
                backgroundColor: _isRoiMode ? Colors.green : null,
                foregroundColor: _isRoiMode ? Colors.white : null,
              ),
            ),
            if (_selectedRect != null) ...[
              const SizedBox(width: 8),
              TextButton.icon(
                onPressed: () {
                  setState(() {
                    _selectedRect = null;
                    _videoStream = null;
                  });
                  _loadThumbnail();
                },
                icon: const Icon(Icons.refresh),
                label: const Text('초기화'),
              ),
            ],
          ],
        ),
      ],
    );
  }

  Widget _buildVideoArea() {
    // 현재 표시되는 영상의 종횡비 계산
    double aspectRatio = widget.videoInfo.width / widget.videoInfo.height;

    // 만약 ROI가 적용된 상태(크롭된 영상 스트리밍/썸네일)라면 해당 비율 사용
    if (_selectedRect != null && !_isRoiMode) {
      aspectRatio = _selectedRect!.width / _selectedRect!.height;
    }

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 400),
        child: AspectRatio(
          aspectRatio: aspectRatio,
          child: _buildVideoContainer(
            Stack(
              fit: StackFit.expand,
              children: [
                if (_videoStream != null)
                  StreamBuilder<ui.Image>(
                    stream: _videoStream,
                    builder: (context, snapshot) {
                      if (snapshot.hasData) {
                        return RawImage(
                          image: snapshot.data!,
                          fit: BoxFit.fill,
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
                    onTap: () {
                      if (!_isRoiMode) {
                        _startStreaming(
                          roi: _convertRectToRoi(
                            _selectedRect,
                            _lastWidgetSize,
                          ),
                        );
                      }
                    },
                    child: Stack(
                      alignment: Alignment.center,
                      fit: StackFit.expand,
                      children: [
                        RawImage(image: _thumbnail!, fit: BoxFit.fill),
                        if (!_isRoiMode)
                          Center(
                            child: Container(
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
                          ),
                      ],
                    ),
                  )
                else if (_isLoadingThumbnail)
                  _buildLoadingWidget('썸네일 로드 중...')
                else
                  _buildErrorWidget('비디오를 로드할 수 없습니다.'),
                if (_isRoiMode)
                  Positioned.fill(
                    child: RoiSelector(
                      videoSize: Size(
                        widget.videoInfo.width.toDouble(),
                        widget.videoInfo.height.toDouble(),
                      ),
                      initialRoi: _selectedRect,
                      onRoiChanged: (rect) {
                        setState(() {
                          _selectedRect = rect;
                        });
                      },
                    ),
                  ),
              ],
            ),
            onSizeLayout: (size) {
              _lastWidgetSize = size;
            },
          ),
        ),
      ),
    );
  }

  Widget _buildVideoContainer(Widget child, {Function(Size)? onSizeLayout}) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // 실제 컨테이너의 크기를 ROI 선택기에 전달하기 위해 측정
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (onSizeLayout != null) {
            final box = context.findRenderObject() as RenderBox?;
            if (box != null && box.hasSize) {
              onSizeLayout(box.size);
            }
          }
        });

        return Container(
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
      },
    );
  }

  Widget _buildLoadingWidget(String message) {
    return Container(
      height: 200,
      width: double.infinity,
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
      width: double.infinity,
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
