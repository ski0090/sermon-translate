import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:caption_extractor/src/rust/api/gstreamer.dart';
import 'package:caption_extractor/src/rust/api/models.dart';
import 'package:flutter_rust_bridge/flutter_rust_bridge_for_generated.dart';
import 'roi_player.dart';
import 'video/video_sidebar.dart';
import 'video/video_screen.dart';
import 'video/video_controls_bar.dart';

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
  final FocusNode _focusNode = FocusNode();
  bool _isSeeking = false;
  int _selectedIntervalMs = 5000; // 기본 5초
  CaptionResult? _currentCaption;
  final List<CaptionResult> _captionHistory = [];

  @override
  void initState() {
    super.initState();
    _loadThumbnail();
    HardwareKeyboard.instance.addHandler(_handleGlobalKeyEvent);
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
    HardwareKeyboard.instance.removeHandler(_handleGlobalKeyEvent);
    _focusNode.dispose();
    super.dispose();
  }

  bool _handleGlobalKeyEvent(KeyEvent event) {
    if (event is! KeyDownEvent) return false;

    if (event.logicalKey == LogicalKeyboardKey.space) {
      _togglePlayPause();
      return true;
    } else if (event.logicalKey == LogicalKeyboardKey.arrowLeft) {
      _seekWithCurrentInterval(-1);
      return true;
    } else if (event.logicalKey == LogicalKeyboardKey.arrowRight) {
      _seekWithCurrentInterval(1);
      return true;
    }
    return false;
  }

  void _seekWithCurrentInterval(int direction) {
    int interval;
    if (_selectedIntervalMs == -1) {
      // 1프레임 계산
      final fps = widget.videoInfo.fps;
      interval = (1000 / (fps > 0 ? fps : 30)).round();
      if (interval == 0) interval = 1;
    } else {
      interval = _selectedIntervalMs;
    }
    _seekRelative(direction * interval);
  }

  void _togglePlayPause() {
    if (_player == null) {
      if (!_isRoiMode) {
        _startStreaming(roi: _selectedRoi);
      }
      return;
    }

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

  Future<void> _seekRelative(int offsetMs) async {
    if (_isSeeking) return;

    final duration = widget.videoInfo.durationMs.toInt();
    int newPosition = (_currentPositionMs + offsetMs).clamp(0, duration);

    setState(() {
      _isSeeking = true;
      _isDragging = true;
      _currentPositionMs = newPosition;
    });

    try {
      if (_videoStream == null) {
        await _startStreaming(roi: _selectedRoi, startTimeMs: newPosition);
        await _player?.pause();
        if (mounted) {
          setState(() {
            _isPlaying = false;
          });
        }
      } else {
        await _player?.seek(timeMs: BigInt.from(newPosition));
      }

      // 안전 장치: 2초 후에도 프레임이 안 오면 강제로 로딩 해제
      Future.delayed(const Duration(seconds: 2)).then((_) {
        if (mounted && _isSeeking) {
          setState(() {
            _isSeeking = false;
            _isDragging = false;
          });
        }
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _isSeeking = false;
          _isDragging = false;
        });
      }
    }
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

    // start()가 이제 Stream<PlayerEvent>를 직접 반환합니다.
    final eventStream = _player!
        .start(
          roi: roi,
          startTimeMs: startTimeMs != null ? BigInt.from(startTimeMs) : null,
        )
        .asBroadcastStream();

    setState(() {
      _isPlaying = true;
      _videoStream = eventStream
          .where((event) => event is PlayerEvent_Video)
          .map((event) => (event as PlayerEvent_Video).field0)
          .where((frame) => !frame.isCropped)
          .map((frame) {
            if (mounted) {
              if (_isSeeking || _isDragging) {
                setState(() {
                  _isSeeking = false;
                  _isDragging = false;
                });
              }
              setState(() {
                _currentPositionMs = frame.timestampMs.toInt();
              });
            }
            return frame;
          })
          .asyncMap(_convertFrameToImage);

      _roiStream = eventStream
          .where((event) => event is PlayerEvent_Video)
          .map((event) => (event as PlayerEvent_Video).field0)
          .where((frame) => frame.isCropped)
          .asyncMap(_convertFrameToImage);
    });

    eventStream.listen((event) {
      if (event is PlayerEvent_Caption) {
        final caption = event.field0;
        if (mounted) {
          setState(() {
            _currentCaption = caption;
            if (_captionHistory.isEmpty ||
                _captionHistory.last.text != caption.text) {
              _captionHistory.add(caption);
            }
          });
        }
      }
    });
  }

  void _onRoiModeToggle() {
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
        _loadRoiThumbnail();
      }
    });
  }

  void _onResetRoi() {
    setState(() {
      _selectedRoi = null;
      _videoStream = null;
      _roiStream = null;
    });
    _loadThumbnail();
  }

  void _onIntervalChanged(int value) {
    setState(() {
      _selectedIntervalMs = value;
    });
  }

  void _onRoiChanged(Roi? roi) {
    if (roi == null) return;
    setState(() {
      _selectedRoi = roi;
    });
    _player?.setRoi(roi: roi);

    // 일시정지 상태라면 현재 위치로 seek하여 프리뷰 스트림 갱신 유도
    if (!_isPlaying && _player != null) {
      _player?.seek(timeMs: BigInt.from(_currentPositionMs));
    }

    _loadRoiThumbnail();
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
            child: VideoPlayerSidebar(
              isRoiMode: _isRoiMode,
              selectedRoi: _selectedRoi,
              selectedIntervalMs: _selectedIntervalMs,
              onRoiModeToggle: _onRoiModeToggle,
              onResetRoi: _onResetRoi,
              onIntervalChanged: _onIntervalChanged,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            flex: 5,
            child: Column(
              children: [
                VideoPlayerScreen(
                  videoStream: _videoStream,
                  thumbnail: _thumbnail,
                  isLoadingThumbnail: _isLoadingThumbnail,
                  isRoiMode: _isRoiMode,
                  selectedRoi: _selectedRoi,
                  videoInfo: widget.videoInfo,
                  isSeeking: _isSeeking,
                  lastWidgetSize: _lastWidgetSize,
                  onRoiChanged: _onRoiChanged,
                  onSizeLayout: (size) {
                    setState(() {
                      _lastWidgetSize = size;
                    });
                  },
                  onTap: () {
                    if (!_isRoiMode) {
                      _togglePlayPause();
                    }
                  },
                ),
                const SizedBox(height: 8),
                VideoPlayerControlsBar(
                  isPlaying: _isPlaying,
                  currentPositionMs: _currentPositionMs,
                  durationMs: widget.videoInfo.durationMs.toInt(),
                  onTogglePlayPause: _togglePlayPause,
                  onSeek: (value) {
                    setState(() {
                      _isDragging = true;
                      _currentPositionMs = value.toInt();
                    });
                    if (_videoStream != null) {
                      _player?.seek(timeMs: BigInt.from(value.toInt()));
                    }
                  },
                  onSeekEnd: (value) async {
                    setState(() {
                      _isSeeking = true;
                      _isDragging = true;
                    });
                    if (_videoStream == null) {
                      await _startStreaming(
                        roi: _selectedRoi,
                        startTimeMs: value.toInt(),
                      );
                    } else {
                      await _player?.seek(timeMs: BigInt.from(value.toInt()));
                    }
                    await _player?.pause();
                    if (mounted) {
                      setState(() {
                        _isPlaying = false;
                      });
                    }

                    // 안전 장치: 2초 타임아웃
                    Future.delayed(const Duration(seconds: 2)).then((_) {
                      if (mounted && _isSeeking) {
                        setState(() {
                          _isSeeking = false;
                          _isDragging = false;
                        });
                      }
                    });
                  },
                ),
                if (_currentCaption != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.black87,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: Colors.blueAccent.withOpacity(0.5),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              '추출된 자막',
                              style: TextStyle(
                                color: Colors.blueAccent,
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              '확신도: ${(_currentCaption!.confidence * 100).toStringAsFixed(1)}%',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.5),
                                fontSize: 10,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _currentCaption!.text,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
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
}
