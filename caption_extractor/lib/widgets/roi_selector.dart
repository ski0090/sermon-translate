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

class _RoiSelectorState extends State<RoiSelector> {
  Offset? _startPos;
  Offset? _currentPos;
  Rect? _currentRoi;

  @override
  void initState() {
    super.initState();
    _currentRoi = widget.initialRoi;
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onPanStart: (details) {
            setState(() {
              _startPos = details.localPosition;
              _currentPos = details.localPosition;
            });
          },
          onPanUpdate: (details) {
            setState(() {
              _currentPos = details.localPosition;
              _updateRoi(constraints.biggest);
            });
          },
          onPanEnd: (details) {
            widget.onRoiChanged(_currentRoi);
            setState(() {
              _startPos = null;
              _currentPos = null;
            });
          },
          child: Container(
            color: Colors.transparent,
            width: double.infinity,
            height: double.infinity,
            child: Stack(
              children: [
                if (_currentRoi != null)
                  Positioned.fromRect(
                    rect: _currentRoi!,
                    child: Container(
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.red, width: 2),
                        color: Colors.red.withAlpha(100),
                      ),
                    ),
                  ),
                if (_startPos != null && _currentPos != null)
                  Positioned.fromRect(
                    rect: Rect.fromPoints(_startPos!, _currentPos!),
                    child: Container(
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.yellow, width: 2),
                        color: Colors.yellow.withAlpha(100),
                      ),
                    ),
                  ),
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
                      _currentRoi == null ? '영역을 드래그하여 선택하세요' : '영역이 선택되었습니다',
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
          ),
        );
      },
    );
  }

  void _updateRoi(Size containerSize) {
    if (_startPos == null || _currentPos == null) return;

    final rect = Rect.fromPoints(_startPos!, _currentPos!);

    // 컨테이너 경계 내로 제한
    final boundedRect = Rect.fromLTRB(
      rect.left.clamp(0.0, containerSize.width),
      rect.top.clamp(0.0, containerSize.height),
      rect.right.clamp(0.0, containerSize.width),
      rect.bottom.clamp(0.0, containerSize.height),
    );

    setState(() {
      _currentRoi = boundedRect;
    });
  }
}
