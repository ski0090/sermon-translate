import 'package:flutter/material.dart';

class RoiSelector extends StatefulWidget {
  final Size videoSize;
  final Rect? initialRoi;
  final Function(Rect?) onRoiChanged;

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
  Rect? _currentRoi;
  _RoiAction _action = _RoiAction.none;

  static const double _handleSize = 12.0;
  static const double _hitAreaSize = 25.0;

  @override
  void initState() {
    super.initState();
    _currentRoi = widget.initialRoi;
  }

  _RoiAction _getHitAction(Offset pos) {
    if (_currentRoi == null) return _RoiAction.creating;

    final rect = _currentRoi!;

    // 상단 왼쪽
    if ((pos - rect.topLeft).distance <= _hitAreaSize) return _RoiAction.resizingTopLeft;
    // 상단 오른쪽
    if ((pos - rect.topRight).distance <= _hitAreaSize) return _RoiAction.resizingTopRight;
    // 하단 왼쪽
    if ((pos - rect.bottomLeft).distance <= _hitAreaSize) return _RoiAction.resizingBottomLeft;
    // 하단 오른쪽
    if ((pos - rect.bottomRight).distance <= _hitAreaSize) return _RoiAction.resizingBottomRight;

    // 내부 이동
    if (rect.contains(pos)) return _RoiAction.moving;

    return _RoiAction.creating;
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final containerSize = constraints.biggest;

        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onPanStart: (details) {
            final action = _getHitAction(details.localPosition);
            setState(() {
              _action = action;
              _startPos = details.localPosition;
              _lastPos = details.localPosition;
              if (action == _RoiAction.creating) {
                _currentRoi = Rect.fromPoints(
                  details.localPosition,
                  details.localPosition,
                );
              }
            });
          },
          onPanUpdate: (details) {
            if (_lastPos == null || (_currentRoi == null && _action != _RoiAction.creating)) return;
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
            widget.onRoiChanged(_currentRoi);
            setState(() {
              _action = _RoiAction.none;
              _startPos = null;
              _lastPos = null;
            });
          },
          child: Stack(
            children: [
              if (_currentRoi != null) ...[
                // 영역 배경 및 테두리
                Positioned.fromRect(
                  rect: _currentRoi!,
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
                // 크기 조절 핸들 (생성 중에는 표시하지 않음)
                if (_action != _RoiAction.creating) ...[
                  _buildHandle(_currentRoi!.topLeft),
                  _buildHandle(_currentRoi!.topRight),
                  _buildHandle(_currentRoi!.bottomLeft),
                  _buildHandle(_currentRoi!.bottomRight),
                ],
              ],
              // 가이드 텍스트
              Positioned(
                top: 10,
                right: 10,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.black54,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    _currentRoi == null
                        ? '영역을 드래그하여 선택하세요'
                        : '영역을 이동하거나 모서리를 드래그하여 조절하세요',
                    style: const TextStyle(color: Colors.white, fontSize: 12),
                  ),
                ),
              ),
              if (_currentRoi != null)
                Positioned(
                  bottom: 10,
                  right: 10,
                  child: IconButton(
                    onPressed: () {
                      setState(() {
                        _currentRoi = null;
                        _action = _RoiAction.none;
                      });
                      widget.onRoiChanged(null);
                    },
                    icon: const Icon(Icons.clear, color: Colors.white),
                    style: IconButton.styleFrom(
                      backgroundColor: Colors.black45,
                    ),
                  ),
                ),
            ],
          ),
        );
      },
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
    if (_currentRoi == null) return;
    var newRect = _currentRoi!.shift(delta);

    // 경계 제한
    double dx = 0;
    double dy = 0;
    if (newRect.left < 0) dx = -newRect.left;
    if (newRect.right > containerSize.width)
      dx = containerSize.width - newRect.right;
    if (newRect.top < 0) dy = -newRect.top;
    if (newRect.bottom > containerSize.height)
      dy = containerSize.height - newRect.bottom;

    _currentRoi = newRect.shift(Offset(dx, dy));
  }

  void _resizeRoi(
    Offset pos,
    Size containerSize, {
    bool topLeft = false,
    bool topRight = false,
    bool bottomLeft = false,
    bool bottomRight = false,
  }) {
    if (_currentRoi == null) return;

    final p = Offset(
      pos.dx.clamp(0.0, containerSize.width),
      pos.dy.clamp(0.0, containerSize.height),
    );
    Rect r = _currentRoi!;

    if (topLeft) {
      _currentRoi = Rect.fromLTRB(p.dx, p.dy, r.right, r.bottom);
    } else if (topRight) {
      _currentRoi = Rect.fromLTRB(r.left, p.dy, p.dx, r.bottom);
    } else if (bottomLeft) {
      _currentRoi = Rect.fromLTRB(p.dx, r.top, r.right, p.dy);
    } else if (bottomRight) {
      _currentRoi = Rect.fromLTRB(r.left, r.top, p.dx, p.dy);
    }
  }

  void _createRoi(Offset pos, Size containerSize) {
    if (_startPos == null) return;
    final r = Rect.fromPoints(_startPos!, pos);
    _currentRoi = Rect.fromLTRB(
      r.left.clamp(0.0, containerSize.width),
      r.top.clamp(0.0, containerSize.height),
      r.right.clamp(0.0, containerSize.width),
      r.bottom.clamp(0.0, containerSize.height),
    );
  }
}
