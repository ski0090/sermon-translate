import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:caption_extractor/src/rust/api/simple.dart';
import '../widgets/video_info_card.dart';
import '../widgets/video_player_view.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String? selectedPath;
  VideoInfo? videoInfo;
  bool isLoading = false;

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['mp4', 'mkv', 'avi'],
    );

    if (result != null && result.files.single.path != null) {
      final path = result.files.single.path!;
      setState(() {
        selectedPath = path;
        isLoading = true;
        videoInfo = null;
      });

      try {
        final info = await getVideoInfo(path: path);
        setState(() {
          videoInfo = info;
          isLoading = false;
        });
      } catch (e) {
        debugPrint('Error getting video info: $e');
        setState(() {
          isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final fileName = selectedPath != null
        ? selectedPath!.split(RegExp(r'[/\\]')).last
        : null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Caption Extractor'),
        actions: [
          IconButton(
            onPressed: _pickFile,
            icon: const Icon(Icons.video_file_outlined),
            tooltip: '영상 파일 선택',
          ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (isLoading)
                const CircularProgressIndicator()
              else if (videoInfo != null) ...[
                VideoInfoCard(fileName: fileName ?? '', videoInfo: videoInfo!),
                const SizedBox(height: 30),
                VideoPlayerView(path: selectedPath!),
              ] else
                Column(
                  children: [
                    const Icon(
                      Icons.video_collection_outlined,
                      size: 60,
                      color: Colors.grey,
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      '파일을 선택해 주세요',
                      style: TextStyle(color: Colors.grey),
                    ),
                    const SizedBox(height: 20),
                    Text(
                      'GStreamer: ${getGstreamerVersion()}',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }
}
