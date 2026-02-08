import 'dart:ui' as ui;
import 'package:flutter/material.dart';

class VideoPlayerControlsBar extends StatelessWidget {
  final bool isPlaying;
  final int currentPositionMs;
  final int durationMs;
  final VoidCallback onTogglePlayPause;
  final ValueChanged<double> onSeek;
  final ValueChanged<double> onSeekEnd;

  const VideoPlayerControlsBar({
    super.key,
    required this.isPlaying,
    required this.currentPositionMs,
    required this.durationMs,
    required this.onTogglePlayPause,
    required this.onSeek,
    required this.onSeekEnd,
  });

  @override
  Widget build(BuildContext context) {
    if (durationMs <= 0) return const SizedBox.shrink();

    return Column(
      children: [
        Row(
          children: [
            IconButton(
              onPressed: onTogglePlayPause,
              icon: Icon(isPlaying ? Icons.pause_circle : Icons.play_circle),
              iconSize: 36,
              color: Colors.blue,
            ),
            Expanded(
              child: SliderTheme(
                data: SliderTheme.of(context).copyWith(
                  trackHeight: 4,
                  thumbShape: const RoundSliderThumbShape(
                    enabledThumbRadius: 6,
                  ),
                  overlayShape: const RoundSliderOverlayShape(
                    overlayRadius: 14,
                  ),
                ),
                child: Slider(
                  value: currentPositionMs.toDouble().clamp(
                    0,
                    durationMs.toDouble(),
                  ),
                  max: durationMs.toDouble(),
                  onChanged: onSeek,
                  onChangeEnd: onSeekEnd,
                ),
              ),
            ),
          ],
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const SizedBox(width: 48), // 재생 버튼 공간 보정
              Text(
                _formatDuration(currentPositionMs),
                style: const TextStyle(
                  fontFeatures: [ui.FontFeature.tabularFigures()],
                ),
              ),
              Text(
                _formatDuration(durationMs),
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
}
