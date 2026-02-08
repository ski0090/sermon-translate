import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/models.dart';
import '../roi_selector.dart';

class VideoPlayerScreen extends StatelessWidget {
  final Stream<ui.Image>? videoStream;
  final ui.Image? thumbnail;
  final bool isLoadingThumbnail;
  final bool isRoiMode;
  final Roi? selectedRoi;
  final VideoInfo videoInfo;
  final bool isSeeking;
  final Size lastWidgetSize;
  final ValueChanged<Roi?> onRoiChanged;
  final ValueChanged<Size> onSizeLayout;
  final VoidCallback onTap;

  const VideoPlayerScreen({
    super.key,
    required this.videoStream,
    required this.thumbnail,
    required this.isLoadingThumbnail,
    required this.isRoiMode,
    required this.selectedRoi,
    required this.videoInfo,
    required this.isSeeking,
    required this.lastWidgetSize,
    required this.onRoiChanged,
    required this.onSizeLayout,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final double aspectRatio = videoInfo.width / videoInfo.height;

    return ConstrainedBox(
      constraints: const BoxConstraints(maxHeight: 500),
      child: AspectRatio(
        aspectRatio: aspectRatio,
        child: _buildVideoContainer(
          Stack(
            fit: StackFit.expand,
            children: [
              if (videoStream != null)
                GestureDetector(
                  onTap: onTap,
                  child: StreamBuilder<ui.Image>(
                    stream: videoStream,
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
              else if (thumbnail != null)
                GestureDetector(
                  onTap: onTap,
                  child: Stack(
                    alignment: Alignment.center,
                    fit: StackFit.expand,
                    children: [
                      RawImage(image: thumbnail!, fit: BoxFit.fill),
                      if (!isRoiMode)
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
              else if (isLoadingThumbnail)
                _buildLoadingWidget('썸네일 로드 중...')
              else
                _buildErrorWidget('비디오를 로드할 수 없습니다.'),
              if (isRoiMode)
                Positioned.fill(
                  child: RoiSelector(
                    videoSize: Size(
                      videoInfo.width.toDouble(),
                      videoInfo.height.toDouble(),
                    ),
                    initialRoi: selectedRoi,
                    onRoiChanged: onRoiChanged,
                  ),
                )
              else if (selectedRoi != null && lastWidgetSize != Size.zero)
                Positioned(
                  left:
                      (selectedRoi!.x / videoInfo.width) * lastWidgetSize.width,
                  top:
                      (selectedRoi!.y / videoInfo.height) *
                      lastWidgetSize.height,
                  width:
                      (selectedRoi!.width / videoInfo.width) *
                      lastWidgetSize.width,
                  height:
                      (selectedRoi!.height / videoInfo.height) *
                      lastWidgetSize.height,
                  child: Container(
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.red, width: 2),
                      color: Colors.red.withAlpha(100),
                    ),
                  ),
                ),
              if (isSeeking)
                Positioned.fill(
                  child: Container(
                    color: Colors.black45,
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const CircularProgressIndicator(color: Colors.white),
                          const SizedBox(height: 16),
                          const Text(
                            '이동 중...',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
            ],
          ),
          onSizeLayout: onSizeLayout,
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
