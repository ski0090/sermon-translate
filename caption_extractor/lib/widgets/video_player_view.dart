import 'dart:ui' as ui;
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:convert';
import 'package:caption_extractor/src/rust/api/gstreamer.dart';
import 'package:caption_extractor/src/rust/api/models.dart';
import 'roi_player.dart';
import 'video/video_sidebar.dart';
import 'video/video_screen.dart';
import 'video/video_controls_bar.dart';
import 'video/caption_timeline.dart';

class CaptionEntry {
  final int startTimeMs;
  int endTimeMs;
  final String text;
  final double confidence;
  final Roi? region;

  CaptionEntry({
    required this.startTimeMs,
    required this.endTimeMs,
    required this.text,
    required this.confidence,
    this.region,
  });

  Map<String, dynamic> toJson() {
    return {
      'start_time_ms': startTimeMs,
      'end_time_ms': endTimeMs,
      'text': text,
      'confidence': double.parse(confidence.toStringAsFixed(4)),
      if (region != null)
        'region': {
          'x': region!.x,
          'y': region!.y,
          'width': region!.width,
          'height': region!.height,
        },
    };
  }
}

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
  bool _isAutoTracking = false;
  int _selectedIntervalMs = 1000; // 기본 5초
  CaptionResult? _currentCaption;
  final List<CaptionEntry> _captionHistory = [];

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

    // 플레이어가 처음 시작될 때 현재 UI 상태(_isAutoTracking)를 Rust 객체에 동기화
    _player?.setAutoTracking(enabled: _isAutoTracking);

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
      if (event is PlayerEvent_AutoRoiUpdated) {
        debugPrint('==== PlayerEvent_AutoRoiUpdated Received! ====');
        if (mounted && _isAutoTracking) {
          // UI 갱신은 부드러운 업데이트를 위해 한 번만 실행
          setState(() {
            _selectedRoi = event.field0;
            if (_isRoiMode) _isRoiMode = false;
          });

          // 백엔드 GStreamer 파이프라인의 ROI 트리밍 필터도 함께 갱신
          _player?.setRoi(roi: event.field0);
          _loadRoiThumbnail();
        }
      } else if (event is PlayerEvent_Caption) {
        final caption = event.field0;
        if (mounted) {
          setState(() {
            _currentCaption = caption;

            if (_captionHistory.isEmpty ||
                _captionHistory.last.text != caption.text) {
              _captionHistory.add(
                CaptionEntry(
                  startTimeMs: caption.timestampMs.toInt(),
                  endTimeMs: caption.timestampMs.toInt() + 500, // 임시 표시 시간
                  text: caption.text,
                  confidence: caption.confidence,
                  region: _selectedRoi,
                ),
              );
            } else {
              // 텍스트가 같다면 종료 시간만 연장
              _captionHistory.last.endTimeMs =
                  caption.timestampMs.toInt() + 500;
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

  Future<void> _onStartBackgroundExtraction() async {
    if (_selectedRoi == null) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('자막을 추출할 영역(ROI)을 먼저 선택해주세요.')),
        );
      }
      return;
    }

    if (_isPlaying) {
      _player?.pause();
      setState(() {
        _isPlaying = false;
      });
    }

    setState(() {
      _captionHistory.clear();
      _currentCaption = null;
    });

    final durationMs = widget.videoInfo.durationMs.toInt();
    double progress = 0.0;
    String statusText = '초기화 중...';
    bool isFinished = false;

    late void Function(void Function()) updateDialog;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            updateDialog = setDialogState;
            return AlertDialog(
              title: const Text('자막 전체 고속 추출'),
              content: SizedBox(
                width: 300,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(statusText),
                    const SizedBox(height: 16),
                    LinearProgressIndicator(
                      value: isFinished ? 1.0 : progress / 100.0,
                      backgroundColor: Colors.grey.shade200,
                    ),
                    const SizedBox(height: 8),
                    Text('${progress.toStringAsFixed(1)}% 완료'),
                  ],
                ),
              ),
              actions: [
                if (isFinished)
                  TextButton(
                    onPressed: () => Navigator.of(ctx).pop(),
                    child: const Text('닫기'),
                  ),
              ],
            );
          },
        );
      },
    );

    try {
      final extractor = await createExtractor(path: widget.path);

      final stream = extractor.start(
        roi: _selectedRoi,
        startTimeMs: null,
        endTimeMs: null,
        totalDurationMs: BigInt.from(durationMs),
      );

      await for (final event in stream) {
        if (!mounted) break;

        if (event is ExtractorEvent_Progress) {
          updateDialog(() {
            progress = event.field0;
            statusText = '전체 영상에서 자막을 추출하고 있습니다...';
          });
        } else if (event is ExtractorEvent_DynamicRoi) {
          if (mounted) {
            setState(() {
              _selectedRoi = event.field0;
            });
            _loadRoiThumbnail();
          }
        } else if (event is ExtractorEvent_Caption) {
          final caption = event.field0;
          setState(() {
            _currentCaption = caption;

            if (_captionHistory.isEmpty ||
                _captionHistory.last.text != caption.text) {
              _captionHistory.add(
                CaptionEntry(
                  startTimeMs: caption.timestampMs.toInt(),
                  endTimeMs: caption.timestampMs.toInt() + 500,
                  text: caption.text,
                  confidence: caption.confidence,
                  region: _selectedRoi,
                ),
              );
            } else {
              _captionHistory.last.endTimeMs =
                  caption.timestampMs.toInt() + 500;
            }
          });
        } else if (event is ExtractorEvent_Finished) {
          updateDialog(() {
            isFinished = true;
            progress = 100.0;
            statusText =
                '추출이 완료되었습니다!\n총 ${_captionHistory.length}개의 자막을 찾았습니다.';
          });
          break;
        } else if (event is ExtractorEvent_Error) {
          updateDialog(() {
            isFinished = true;
            statusText = '오류 발생: ${event.field0}';
          });
          break;
        }
      }
    } catch (e) {
      updateDialog(() {
        isFinished = true;
        statusText = '예외 발생: $e';
      });
    }
  }

  Future<void> _onAutoRoiDetection() async {
    // 혹시 재생 중이라면 일시 정지
    if (_isPlaying) {
      _player?.pause();
      setState(() {
        _isPlaying = false;
      });
    }

    // 로딩 등 사용자 피드백을 보여주는 것도 좋지만, 현재는 바로 호출
    try {
      final detectedRoi = await autoDetectRoiForTime(
        path: widget.path,
        timeMs: BigInt.from(_currentPositionMs),
      );

      if (detectedRoi != null) {
        setState(() {
          _selectedRoi = detectedRoi;
          // 만약 현재 수동 영역 모드가 아니라면 해제
          if (_isRoiMode) {
            _isRoiMode = false;
          }
        });

        _player?.setRoi(roi: detectedRoi);
        _loadRoiThumbnail();

        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('자막 영역을 자동으로 감지했습니다.')));
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('현재 화면에서 자막 영역을 찾지 못했습니다.')),
          );
        }
      }
    } catch (e) {
      debugPrint('Auto ROI detection error: $e');
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('자동 영역 감지 중 오류가 발생했습니다: $e')));
      }
    }
  }

  void _onAutoTrackingToggle(bool value) {
    debugPrint('==== Auto Tracking Toggle: $value ====');
    setState(() {
      _isAutoTracking = value;
    });
    _player?.setAutoTracking(enabled: value);

    if (value && mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('실시간 자막 영역 자동 추적을 시작합니다.')));
    }
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

  Future<void> _saveJson() async {
    if (_captionHistory.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('저장할 자막 데이터가 없습니다.')));
      }
      return;
    }

    try {
      String? outputFile = await FilePicker.platform.saveFile(
        dialogTitle: '자막 저장',
        fileName: 'captions.json',
        type: FileType.custom,
        allowedExtensions: ['json'],
      );

      if (outputFile != null) {
        final List<Map<String, dynamic>> jsonList = _captionHistory
            .map((e) => e.toJson())
            .toList();
        final String jsonString = const JsonEncoder.withIndent(
          '  ',
        ).convert(jsonList);

        final file = File(outputFile);
        await file.writeAsString(jsonString, encoding: utf8);

        if (mounted) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text('파일이 저장되었습니다: $outputFile')));
        }
      }
    } catch (e) {
      debugPrint('Error saving JSON: $e');
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('저장 중 오류가 발생했습니다: $e')));
      }
    }
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
              isAutoTracking: _isAutoTracking,
              selectedRoi: _selectedRoi,
              selectedIntervalMs: _selectedIntervalMs,
              onAutoRoiDetection: _onAutoRoiDetection,
              onAutoTrackingToggle: _onAutoTrackingToggle,
              onRoiModeToggle: _onRoiModeToggle,
              onResetRoi: _onResetRoi,
              onIntervalChanged: _onIntervalChanged,
              onSaveJson: _captionHistory.isNotEmpty ? _saveJson : null,
              onStartBackgroundExtraction: _onStartBackgroundExtraction,
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
                        color: Colors.blueAccent.withValues(alpha: 0.5),
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
                                color: Colors.white.withValues(alpha: 0.5),
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
            child: Column(
              children: [
                const SizedBox(
                  width: double.infinity,
                  child: Text(
                    '크롭된 화면 (ROI)',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                ),
                const SizedBox(height: 8),
                AspectRatio(
                  aspectRatio: 16 / 9,
                  child: RoiPlayer(
                    roiStream: _roiStream,
                    staticImage: _roiThumbnail,
                  ),
                ),
                const SizedBox(height: 16),
                const SizedBox(
                  width: double.infinity,
                  child: Text(
                    '추출된 자막 타임라인',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                ),
                const SizedBox(height: 8),
                const SizedBox(height: 8),
                Container(
                  height: 350,
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.grey.shade300),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: CaptionTimeline(
                    captions: _captionHistory,
                    onSeekTo: (timeMs) {
                      setState(() {
                        _isDragging = true;
                        _currentPositionMs = timeMs;
                      });
                      if (_videoStream != null) {
                        _player?.seek(timeMs: BigInt.from(timeMs));
                      }

                      // SeekEnd 유사 루틴 (안전 장치 포함)
                      Future.delayed(const Duration(milliseconds: 300)).then((
                        _,
                      ) async {
                        if (!mounted) return;

                        setState(() {
                          _isSeeking = true;
                          _isDragging = true;
                        });

                        if (_videoStream == null) {
                          await _startStreaming(
                            roi: _selectedRoi,
                            startTimeMs: timeMs,
                          );
                        } else {
                          await _player?.seek(timeMs: BigInt.from(timeMs));
                        }
                        await _player?.pause();
                        if (mounted) {
                          setState(() {
                            _isPlaying = false;
                          });
                        }

                        Future.delayed(const Duration(seconds: 2)).then((_) {
                          if (mounted && _isSeeking) {
                            setState(() {
                              _isSeeking = false;
                              _isDragging = false;
                            });
                          }
                        });
                      });
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
