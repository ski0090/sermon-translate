import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/simple.dart';
import 'roi_selector.dart';
import 'roi_player.dart';

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
  Stream<ui.Image>? _roiStream;
  NativePlayer? _player;
  ui.Image? _thumbnail;
  bool _isLoadingThumbnail = false;
  Roi? _selectedRoi;
  ui.Image? _roiThumbnail;
  bool _isRoiMode = false;
  int _currentPositionMs = 0;
  bool _isPlaying = false;
  bool _isDragging = false;
  Size _lastWidgetSize = Size.zero;

  @override
  void initState() {
    super.initState();
    _loadThumbnail();
  }

  @override
  void didUpdateWidget(VideoPlayerView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.path != widget.path) {
      if (_player != null) {
        _player!.stop();
        _player = null;
      }
      setState(() {
        _videoStream = null;
        _roiStream = null;
        _thumbnail = null;
        _selectedRoi = null;
        _isRoiMode = false;
      });
      _loadThumbnail();
    }
  }

  @override
  void dispose() {
    _player?.stop();
    super.dispose();
  }

  Future<void> _loadThumbnail({Roi? roi, int? timeMs}) async {
    setState(() {
      _isLoadingThumbnail = true;
    });

    try {
      final frame = await getFrame(
        path: widget.path,
        roi: roi,
        timeMs: timeMs != null ? BigInt.from(timeMs) : null,
      );
      final image = await _convertFrameToImage(frame);

      if (mounted) {
        setState(() {
          _thumbnail = image;
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

  Future<void> _loadRoiThumbnail() async {
    if (_selectedRoi == null) return;

    try {
      final frame = await getFrame(
        path: widget.path,
        roi: _selectedRoi,
        timeMs: BigInt.from(_currentPositionMs),
      );
      final image = await _convertFrameToImage(frame);

      if (mounted) {
        setState(() {
          _roiThumbnail = image;
        });
      }
    } catch (e) {
      debugPrint('ROI Thumbnail loading error: $e');
    }
  }

  Future<ui.Image> _convertFrameToImage(VideoFrame frame) async {
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
  }

  Future<void> _startStreaming({Roi? roi, int? startTimeMs}) async {
    if (_player == null) {
      try {
        _player = await createPlayer(path: widget.path);
      } catch (e) {
        debugPrint('Failed to create player: $e');
        return;
      }
    }

    final baseStream = _player!
        .start(
          roi: roi,
          startTimeMs: startTimeMs != null ? BigInt.from(startTimeMs) : null,
        )
        .asBroadcastStream();

    setState(() {
      _isPlaying = true;
      _videoStream = baseStream
          .where((frame) => !frame.isCropped)
          .map((frame) {
            if (mounted && !_isDragging) {
              setState(() {
                _currentPositionMs = frame.timestampMs.toInt();
              });
            }
            return frame;
          })
          .asyncMap(_convertFrameToImage);

      _roiStream = baseStream
          .where((frame) => frame.isCropped)
          .asyncMap(_convertFrameToImage);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 1,
            child: Column(
              children: [
                ElevatedButton.icon(
                  onPressed: () {
                    setState(() {
                      _isRoiMode = !_isRoiMode;
                      if (_isRoiMode) {
                        _player?.pause();
                        _isPlaying = false;
                        _loadThumbnail(roi: null, timeMs: _currentPositionMs);

                        // 클릭한 시점을 ROI 시작 시간으로 설정
                        if (_selectedRoi == null) {
                          _selectedRoi = Roi(
                            x: 0,
                            y: 0,
                            width: 0,
                            height: 0,
                            startTimeMs: BigInt.from(_currentPositionMs),
                            endTimeMs: BigInt.zero,
                          );
                        } else {
                          final old = _selectedRoi!;
                          _selectedRoi = Roi(
                            x: old.x,
                            y: old.y,
                            width: old.width,
                            height: old.height,
                            startTimeMs: BigInt.from(_currentPositionMs),
                            endTimeMs: old.endTimeMs,
                          );
                        }

                        _loadRoiThumbnail();
                      } else {
                        _player?.setRoi(roi: _selectedRoi);
                        _player?.resume();
                        _isPlaying = true;
                      }
                    });
                  },
                  icon: Icon(_isRoiMode ? Icons.check : Icons.crop),
                  label: const Text('영역 선택', overflow: TextOverflow.ellipsis),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isRoiMode ? Colors.green : null,
                    foregroundColor: _isRoiMode ? Colors.white : null,
                    minimumSize: const Size(double.infinity, 48),
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                  ),
                ),
                if (_selectedRoi != null) ...[
                  const SizedBox(height: 12),
                  TextButton.icon(
                    onPressed: () {
                      setState(() {
                        _selectedRoi = null;
                        _videoStream = null;
                        _roiStream = null;
                      });
                      _loadThumbnail();
                    },
                    icon: const Icon(Icons.refresh),
                    label: const Text('초기화', overflow: TextOverflow.ellipsis),
                    style: TextButton.styleFrom(
                      minimumSize: const Size(double.infinity, 48),
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            flex: 5,
            child: Column(
              children: [
                _buildVideoArea(),
                const SizedBox(height: 8),
                _buildPlayerControls(),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            flex: 2,
            child: RoiPlayer(roiStream: _roiStream, staticImage: _roiThumbnail),
          ),
        ],
      ),
    );
  }

  Widget _buildVideoArea() {
    final double aspectRatio = widget.videoInfo.width / widget.videoInfo.height;

    return ConstrainedBox(
      constraints: const BoxConstraints(maxHeight: 500),
      child: AspectRatio(
        aspectRatio: aspectRatio,
        child: _buildVideoContainer(
          Stack(
            fit: StackFit.expand,
            children: [
              if (_videoStream != null)
                GestureDetector(
                  onTap: () {
                    if (!_isRoiMode && _player != null) {
                      setState(() {
                        if (_isPlaying) {
                          _player!.pause();
                          _isPlaying = false;
                        } else {
                          _player!.resume();
                          _isPlaying = true;
                        }
                      });
                    }
                  },
                  child: StreamBuilder<ui.Image>(
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
                  ),
                )
              else if (_thumbnail != null)
                GestureDetector(
                  onTap: () {
                    if (!_isRoiMode) {
                      _startStreaming(roi: _selectedRoi);
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
                    initialRoi: _selectedRoi,
                    onRoiChanged: (roi) {
                      setState(() {
                        _selectedRoi = roi;
                      });
                      _player?.setRoi(roi: roi);
                      _loadRoiThumbnail();
                    },
                  ),
                )
              else if (_selectedRoi != null)
                Positioned(
                  left:
                      (_selectedRoi!.x / widget.videoInfo.width) *
                      _lastWidgetSize.width,
                  top:
                      (_selectedRoi!.y / widget.videoInfo.height) *
                      _lastWidgetSize.height,
                  width:
                      (_selectedRoi!.width / widget.videoInfo.width) *
                      _lastWidgetSize.width,
                  height:
                      (_selectedRoi!.height / widget.videoInfo.height) *
                      _lastWidgetSize.height,
                  child: Container(
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.red, width: 2),
                      color: Colors.red.withAlpha(100),
                    ),
                  ),
                ),
            ],
          ),
          onSizeLayout: (size) {
            _lastWidgetSize = size;
          },
        ),
      ),
    );
  }

  Widget _buildVideoContainer(Widget child, {Function(Size)? onSizeLayout}) {
    return LayoutBuilder(
      builder: (context, constraints) {
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
            border: Border.all(color: Colors.blue.withAlpha(100), width: 2),
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withAlpha(100),
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

  Widget _buildPlayerControls() {
    final duration = widget.videoInfo.durationMs.toInt();
    if (duration <= 0) return const SizedBox.shrink();

    return Column(
      children: [
        SliderTheme(
          data: SliderTheme.of(context).copyWith(
            trackHeight: 4,
            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
            overlayShape: const RoundSliderOverlayShape(overlayRadius: 14),
          ),
          child: Slider(
            value: _currentPositionMs.toDouble().clamp(0, duration.toDouble()),
            max: duration.toDouble(),
            onChanged: (value) {
              setState(() {
                _isDragging = true;
                _currentPositionMs = value.toInt();
              });
              if (_videoStream != null) {
                _player?.seek(timeMs: BigInt.from(value.toInt()));
              }
            },
            onChangeEnd: (value) async {
              if (_videoStream == null) {
                await _startStreaming(
                  roi: _selectedRoi,
                  startTimeMs: value.toInt(),
                );
              } else {
                await _player?.seek(timeMs: BigInt.from(value.toInt()));
              }
              await _player?.pause();
              setState(() {
                _isPlaying = false;
                _isDragging = false;
              });
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _formatDuration(_currentPositionMs),
                style: const TextStyle(
                  fontFeatures: [ui.FontFeature.tabularFigures()],
                ),
              ),
              Text(
                _formatDuration(duration),
                style: const TextStyle(
                  fontFeatures: [ui.FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  String _formatDuration(int ms) {
    final totalSeconds = ms ~/ 1000;
    final minutes = totalSeconds ~/ 60;
    final seconds = totalSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
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
