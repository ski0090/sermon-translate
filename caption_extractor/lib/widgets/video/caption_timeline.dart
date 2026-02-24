import 'package:flutter/material.dart';
import 'package:caption_extractor/widgets/video_player_view.dart'
    show CaptionEntry;

class CaptionTimeline extends StatelessWidget {
  final List<CaptionEntry> captions;
  final ValueChanged<int> onSeekTo;

  const CaptionTimeline({
    super.key,
    required this.captions,
    required this.onSeekTo,
  });

  String _formatTime(int ms) {
    final duration = Duration(milliseconds: ms);
    final minutes = duration.inMinutes.toString().padLeft(2, '0');
    final seconds = (duration.inSeconds % 60).toString().padLeft(2, '0');
    final millis = (duration.inMilliseconds % 1000).toString().padLeft(3, '0');
    return '$minutes:$seconds.$millis';
  }

  @override
  Widget build(BuildContext context) {
    if (captions.isEmpty) {
      return const Center(
        child: Text('추출된 자막이 없습니다.', style: TextStyle(color: Colors.grey)),
      );
    }

    return ListView.builder(
      itemCount: captions.length,
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemBuilder: (context, index) {
        // 최신 자막이 위에 보이도록 역순으로 보여주는 것도 하나의 방법이긴 하나,
        // 타임라인이라는 특징상 정방향 시간순(가끔 마지막 아이템 포커싱)이 어울릴 수 있습니다.
        // 현재는 시간순(정방향)으로 나열합니다.
        final entry = captions[index];
        final timeStr =
            '${_formatTime(entry.startTimeMs)} ~ ${_formatTime(entry.endTimeMs)}';

        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          elevation: 1,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: BorderSide(color: Colors.grey.shade300),
          ),
          child: InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: () => onSeekTo(entry.startTimeMs),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        timeStr,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.blueAccent,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        '확신도: ${(entry.confidence * 100).toStringAsFixed(1)}%',
                        style: TextStyle(
                          fontSize: 10,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    entry.text,
                    style: const TextStyle(fontSize: 14, height: 1.4),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
