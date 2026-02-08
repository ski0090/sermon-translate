import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/simple.dart';

class RoiSelector extends StatefulWidget {
  final Size videoSize;
  final Roi? initialRoi;
  final Function(Roi?) onRoiChanged;

  const RoiSelector({
    super.key,
    required this.videoSize,
    this.initialRoi,
    required this.onRoiChanged,
  });

  @override
  State<RoiSelector> createState() => _RoiSelectorState();
}

enum _RoiAction {
  none,
  moving,
  resizingTopLeft,
  resizingTopRight,
  resizingBottomLeft,
  resizingBottomRight,
  creating,
}

class _RoiSelectorState extends State<RoiSelector> {
  Offset? _startPos;
  Offset? _lastPos;
  Rect? _currentRect;
  BigInt _startTimeMs = BigInt.zero;
  BigInt _endTimeMs = BigInt.zero;
  _RoiAction _action = _RoiAction.none;

  final TextEditingController _startController = TextEditingController();
  final TextEditingController _endController = TextEditingController();

  static const double _handleSize = 12.0;
  static const double _hitAreaSize = 25.0;

  @override
  void initState() {
    super.initState();
    if (widget.initialRoi != null) {
      final roi = widget.initialRoi!;
      _startTimeMs = roi.startTimeMs;
      _endTimeMs = roi.endTimeMs;
      _startController.text = _formatMs(_startTimeMs);
      _endController.text = _formatMs(_endTimeMs);
    }
  }

  @override
  void dispose() {
    _startController.dispose();
    _endController.dispose();
    super.dispose();
  }

  void _notifyChanged(Size containerSize) {
    if (_currentRect == null) {
      widget.onRoiChanged(null);
      return;
    }

    final vWidth = widget.videoSize.width;
    final vHeight = widget.videoSize.height;

    final scaleX = vWidth / containerSize.width;
    final scaleY = vHeight / containerSize.height;

    final roi = Roi(
      x: (_currentRect!.left * scaleX).toInt(),
      y: (_currentRect!.top * scaleY).toInt(),
      width: (_currentRect!.width * scaleX).toInt(),
      height: (_currentRect!.height * scaleY).toInt(),
      startTimeMs: _startTimeMs,
      endTimeMs: _endTimeMs,
    );

    widget.onRoiChanged(roi);
  }

  _RoiAction _getHitAction(Offset pos) {
    if (_currentRect == null) return _RoiAction.creating;

    final rect = _currentRect!;

    if ((pos - rect.topLeft).distance <= _hitAreaSize)
      return _RoiAction.resizingTopLeft;
    if ((pos - rect.topRight).distance <= _hitAreaSize)
      return _RoiAction.resizingTopRight;
    if ((pos - rect.bottomLeft).distance <= _hitAreaSize)
      return _RoiAction.resizingBottomLeft;
    if ((pos - rect.bottomRight).distance <= _hitAreaSize)
      return _RoiAction.resizingBottomRight;

    if (rect.contains(pos)) return _RoiAction.moving;

    return _RoiAction.creating;
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final containerSize = constraints.biggest;

        // 초기 Roi가 있고 _currentRect가 없는 경우 변환
        if (widget.initialRoi != null &&
            _currentRect == null &&
            containerSize != Size.zero) {
          final roi = widget.initialRoi!;
          final vWidth = widget.videoSize.width;
          final vHeight = widget.videoSize.height;
          final scaleX = containerSize.width / vWidth;
          final scaleY = containerSize.height / vHeight;

          _currentRect = Rect.fromLTWH(
            roi.x * scaleX,
            roi.y * scaleY,
            roi.width * scaleX,
            roi.height * scaleY,
          );
        }

        return Stack(
          children: [
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onPanStart: (details) {
                final action = _getHitAction(details.localPosition);
                setState(() {
                  _action = action;
                  _startPos = details.localPosition;
                  _lastPos = details.localPosition;
                  if (action == _RoiAction.creating) {
                    _currentRect = Rect.fromPoints(
                      details.localPosition,
                      details.localPosition,
                    );
                  }
                });
              },
              onPanUpdate: (details) {
                if (_lastPos == null ||
                    (_currentRect == null && _action != _RoiAction.creating))
                  return;
                final delta = details.localPosition - _lastPos!;

                setState(() {
                  switch (_action) {
                    case _RoiAction.moving:
                      _moveRoi(delta, containerSize);
                      break;
                    case _RoiAction.resizingTopLeft:
                      _resizeRoi(
                        details.localPosition,
                        containerSize,
                        topLeft: true,
                      );
                      break;
                    case _RoiAction.resizingTopRight:
                      _resizeRoi(
                        details.localPosition,
                        containerSize,
                        topRight: true,
                      );
                      break;
                    case _RoiAction.resizingBottomLeft:
                      _resizeRoi(
                        details.localPosition,
                        containerSize,
                        bottomLeft: true,
                      );
                      break;
                    case _RoiAction.resizingBottomRight:
                      _resizeRoi(
                        details.localPosition,
                        containerSize,
                        bottomRight: true,
                      );
                      break;
                    case _RoiAction.creating:
                      _createRoi(details.localPosition, containerSize);
                      break;
                    default:
                      break;
                  }
                  _lastPos = details.localPosition;
                });
              },
              onPanEnd: (details) {
                _notifyChanged(containerSize);
                setState(() {
                  _action = _RoiAction.none;
                  _startPos = null;
                  _lastPos = null;
                });
              },
              child: Stack(
                children: [
                  if (_currentRect != null) ...[
                    Positioned.fromRect(
                      rect: _currentRect!,
                      child: Container(
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: _action == _RoiAction.creating
                                ? Colors.yellow
                                : Colors.red,
                            width: 2,
                          ),
                          color:
                              (_action == _RoiAction.creating
                                      ? Colors.yellow
                                      : Colors.red)
                                  .withAlpha(100),
                        ),
                      ),
                    ),
                    if (_action != _RoiAction.creating) ...[
                      _buildHandle(_currentRect!.topLeft),
                      _buildHandle(_currentRect!.topRight),
                      _buildHandle(_currentRect!.bottomLeft),
                      _buildHandle(_currentRect!.bottomRight),
                    ],
                  ],
                ],
              ),
            ),
            // 가이드 및 시간 설정 UI
            Positioned(
              top: 10,
              right: 10,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.black54,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      _currentRect == null
                          ? '영역을 드래그하여 선택하세요'
                          : '영역을 이동하거나 조절하세요',
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                  ),
                  const SizedBox(height: 8),
                  if (_currentRect != null) _buildTimeInput(containerSize),
                ],
              ),
            ),
            if (_currentRect != null)
              Positioned(
                bottom: 10,
                right: 10,
                child: IconButton(
                  onPressed: () {
                    setState(() {
                      _currentRect = null;
                      _action = _RoiAction.none;
                    });
                    widget.onRoiChanged(null);
                  },
                  icon: const Icon(Icons.clear, color: Colors.white),
                  style: IconButton.styleFrom(backgroundColor: Colors.black45),
                ),
              ),
          ],
        );
      },
    );
  }

  Widget _buildTimeInput(Size containerSize) {
    return Container(
      width: 200,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.black87,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildTimeField('시작', _startController, (val) {
            setState(() => _startTimeMs = _parseMs(val));
            _notifyChanged(containerSize);
          }),
          const SizedBox(height: 4),
          _buildTimeField('종료', _endController, (val) {
            setState(() => _endTimeMs = _parseMs(val));
            _notifyChanged(containerSize);
          }),
        ],
      ),
    );
  }

  String _formatMs(BigInt ms) {
    final totalSeconds = ms.toInt() ~/ 1000;
    final minutes = totalSeconds ~/ 60;
    final seconds = totalSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  BigInt _parseMs(String text) {
    if (text.isEmpty) return BigInt.zero;
    
    final parts = text.split(':');
    if (parts.length == 2) {
      final minutes = int.tryParse(parts[0]) ?? 0;
      final seconds = int.tryParse(parts[1]) ?? 0;
      return BigInt.from((minutes * 60 + seconds) * 1000);
    }
    
    // 포맷이 맞지 않으면 숫자로만 파싱 시도 (기존 호환성)
    return BigInt.tryParse(text) ?? BigInt.zero;
  }

  Widget _buildTimeField(
    String label,
    TextEditingController controller,
    Function(String) onChanged,
  ) {
    return Row(
      children: [
        SizedBox(
          width: 60,
          child: Text(
            label,
            style: const TextStyle(color: Colors.white, fontSize: 10),
          ),
        ),
        Expanded(
          child: SizedBox(
            height: 30,
            child: TextField(
              controller: controller,
              style: const TextStyle(color: Colors.white, fontSize: 12),
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                contentPadding: EdgeInsets.symmetric(horizontal: 8),
                border: OutlineInputBorder(),
                enabledBorder: OutlineInputBorder(
                  borderSide: BorderSide(color: Colors.white24),
                ),
              ),
              onChanged: onChanged,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildHandle(Offset center) {
    return Positioned(
      left: center.dx - _handleSize / 2,
      top: center.dy - _handleSize / 2,
      child: Container(
        width: _handleSize,
        height: _handleSize,
        decoration: const BoxDecoration(
          color: Colors.white,
          shape: BoxShape.circle,
          boxShadow: [BoxShadow(blurRadius: 2, color: Colors.black26)],
        ),
      ),
    );
  }

  void _moveRoi(Offset delta, Size containerSize) {
    if (_currentRect == null) return;
    var newRect = _currentRect!.shift(delta);

    double dx = 0, dy = 0;
    if (newRect.left < 0) dx = -newRect.left;
    if (newRect.right > containerSize.width)
      dx = containerSize.width - newRect.right;
    if (newRect.top < 0) dy = -newRect.top;
    if (newRect.bottom > containerSize.height)
      dy = containerSize.height - newRect.bottom;

    _currentRect = newRect.shift(Offset(dx, dy));
  }

  void _resizeRoi(
    Offset pos,
    Size containerSize, {
    bool topLeft = false,
    bool topRight = false,
    bool bottomLeft = false,
    bool bottomRight = false,
  }) {
    if (_currentRect == null) return;
    final p = Offset(
      pos.dx.clamp(0.0, containerSize.width),
      pos.dy.clamp(0.0, containerSize.height),
    );
    Rect r = _currentRect!;

    if (topLeft) {
      _currentRect = Rect.fromLTRB(p.dx, p.dy, r.right, r.bottom);
    } else if (topRight) {
      _currentRect = Rect.fromLTRB(r.left, p.dy, p.dx, r.bottom);
    } else if (bottomLeft) {
      _currentRect = Rect.fromLTRB(p.dx, r.top, r.right, p.dy);
    } else if (bottomRight) {
      _currentRect = Rect.fromLTRB(r.left, r.top, p.dx, p.dy);
    }
  }

  void _createRoi(Offset pos, Size containerSize) {
    if (_startPos == null) return;
    final r = Rect.fromPoints(_startPos!, pos);
    _currentRect = Rect.fromLTRB(
      r.left.clamp(0.0, containerSize.width),
      r.top.clamp(0.0, containerSize.height),
      r.right.clamp(0.0, containerSize.width),
      r.bottom.clamp(0.0, containerSize.height),
    );
  }
}
