import 'dart:ui' as ui;
import 'package:flutter/material.dart';

class RoiPlayer extends StatelessWidget {
  final Stream<ui.Image>? roiStream;
  final ui.Image? staticImage;
  final String title;

  const RoiPlayer({
    super.key,
    required this.roiStream,
    this.staticImage,
    this.title = '크롭된 화면 (ROI)',
  });

  @override
  Widget build(BuildContext context) {
    if (roiStream == null) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Container(
          height: 200,
          width: double.infinity,
          decoration: BoxDecoration(
            color: Colors.black12,
            border: Border.all(color: Colors.red.withAlpha(100), width: 2),
            borderRadius: BorderRadius.circular(12),
          ),
          clipBehavior: Clip.antiAlias,
          child: StreamBuilder<ui.Image>(
            stream: roiStream,
            builder: (context, snapshot) {
              if (snapshot.hasData) {
                return RawImage(image: snapshot.data!, fit: BoxFit.contain);
              }
              if (staticImage != null) {
                return RawImage(image: staticImage!, fit: BoxFit.contain);
              }
              if (snapshot.hasError) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(8.0),
                    child: Text(
                      '오류: ${snapshot.error}',
                      style: const TextStyle(fontSize: 12, color: Colors.red),
                      textAlign: TextAlign.center,
                    ),
                  ),
                );
              }
              return const Center(
                child: Text(
                  'ROI 데이터 대기 중...',
                  style: TextStyle(fontSize: 12, color: Colors.grey),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}
