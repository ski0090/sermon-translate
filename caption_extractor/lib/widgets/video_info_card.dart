import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/simple.dart';

class VideoInfoCard extends StatelessWidget {
  final String fileName;
  final VideoInfo videoInfo;

  const VideoInfoCard({
    super.key,
    required this.fileName,
    required this.videoInfo,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                const Icon(Icons.movie_outlined, color: Colors.blue),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    fileName,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 18,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const Divider(height: 10),
            _infoItem(
              Icons.aspect_ratio,
              '해상도',
              '${videoInfo.width} x ${videoInfo.height}',
            ),
            _infoItem(
              Icons.timer_outlined,
              '재생 시간',
              '${(videoInfo.durationMs.toDouble() / 1000).toStringAsFixed(2)} 초',
            ),
            _infoItem(
              Icons.slow_motion_video,
              '프레임 레이트',
              '${videoInfo.fps.toStringAsFixed(2)} fps',
            ),
            _infoItem(Icons.code, '포맷', videoInfo.format),
          ],
        ),
      ),
    );
  }

  Widget _infoItem(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 18, color: Colors.grey[600]),
          const SizedBox(width: 10),
          Text('$label: ', style: TextStyle(color: Colors.grey[700])),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }
}
