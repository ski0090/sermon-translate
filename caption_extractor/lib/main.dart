import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/simple.dart';
import 'package:caption_extractor/src/rust/frb_generated.dart';

import 'package:file_picker/file_picker.dart';

Future<void> main() async {
  await RustLib.init();
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  String? selectedPath;

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['mp4', 'mkv', 'avi'],
    );

    if (result != null && result.files.single.path != null) {
      setState(() {
        selectedPath = result.files.single.path;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        appBar: AppBar(title: const Text('Caption Extractor')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('GStreamer: ${getGstreamerVersion()}'),
              const SizedBox(height: 20),
              if (selectedPath != null)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Text(
                    'Selected: $selectedPath',
                    textAlign: TextAlign.center,
                  ),
                ),
              const SizedBox(height: 10),
              ElevatedButton(
                onPressed: _pickFile,
                child: const Text('영상 파일 선택'),
              ),
              if (selectedPath != null)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: ElevatedButton(
                    onPressed: () async {
                      try {
                        await playVideo(path: selectedPath!);
                      } catch (e) {
                        debugPrint('Error playing video: $e');
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                    ),
                    child: const Text('GStreamer로 재생'),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
