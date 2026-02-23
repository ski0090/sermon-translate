import 'package:flutter/material.dart';
import 'package:caption_extractor/src/rust/api/models.dart';

class VideoPlayerSidebar extends StatelessWidget {
  final bool isRoiMode;
  final Roi? selectedRoi;
  final int selectedIntervalMs;
  final VoidCallback onRoiModeToggle;
  final VoidCallback onAutoRoiDetection;
  final bool isAutoTracking;
  final ValueChanged<bool> onAutoTrackingToggle;
  final VoidCallback onResetRoi;
  final ValueChanged<int> onIntervalChanged;
  final VoidCallback? onSaveJson;

  const VideoPlayerSidebar({
    super.key,
    required this.isRoiMode,
    required this.selectedRoi,
    required this.selectedIntervalMs,
    required this.onAutoRoiDetection,
    required this.isAutoTracking,
    required this.onAutoTrackingToggle,
    required this.onRoiModeToggle,
    required this.onResetRoi,
    required this.onIntervalChanged,
    this.onSaveJson,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ElevatedButton.icon(
          onPressed: onRoiModeToggle,
          icon: Icon(isRoiMode ? Icons.check : Icons.crop),
          label: const Text('영역 선택', overflow: TextOverflow.ellipsis),
          style: ElevatedButton.styleFrom(
            backgroundColor: isRoiMode ? Colors.green : null,
            foregroundColor: isRoiMode ? Colors.white : null,
            minimumSize: const Size(double.infinity, 48),
            padding: const EdgeInsets.symmetric(horizontal: 4),
          ),
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey.shade300),
            borderRadius: BorderRadius.circular(8),
          ),
          child: SwitchListTile(
            title: const Text(
              '실시간 자막 추적',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
            ),
            value: isAutoTracking,
            onChanged: onAutoTrackingToggle,
            contentPadding: const EdgeInsets.symmetric(horizontal: 8),
            dense: true,
          ),
        ),
        if (selectedRoi != null) ...[
          const SizedBox(height: 12),
          TextButton.icon(
            onPressed: onAutoRoiDetection,
            icon: const Icon(Icons.auto_awesome),
            label: const Text('현재 영역 자동 감지', overflow: TextOverflow.ellipsis),
            style: TextButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
              padding: const EdgeInsets.symmetric(horizontal: 4),
            ),
          ),
          const SizedBox(height: 12),
          TextButton.icon(
            onPressed: onResetRoi,
            icon: const Icon(Icons.refresh),
            label: const Text('초기화', overflow: TextOverflow.ellipsis),
            style: TextButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
              padding: const EdgeInsets.symmetric(horizontal: 4),
              foregroundColor: Colors.red,
            ),
          ),
          if (onSaveJson != null) ...[
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: onSaveJson,
              icon: const Icon(Icons.save),
              label: const Text('JSON 저장', overflow: TextOverflow.ellipsis),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(double.infinity, 48),
                padding: const EdgeInsets.symmetric(horizontal: 4),
              ),
            ),
          ],
        ],
        const SizedBox(height: 24),
        const Divider(),
        const SizedBox(height: 12),
        const Text(
          '이동 단위',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
        ),
        const SizedBox(height: 8),
        _buildIntervalOption('1프레임', -1),
        _buildIntervalOption('0.5초', 500),
        _buildIntervalOption('1초', 1000),
        _buildIntervalOption('5초', 5000),
        _buildIntervalOption('10초', 10000),
      ],
    );
  }

  Widget _buildIntervalOption(String label, int value) {
    final isSelected = selectedIntervalMs == value;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: OutlinedButton(
        onPressed: () => onIntervalChanged(value),
        style: OutlinedButton.styleFrom(
          backgroundColor: isSelected ? Colors.blue.shade50 : null,
          side: BorderSide(
            color: isSelected ? Colors.blue : Colors.grey.shade300,
            width: isSelected ? 2 : 1,
          ),
          foregroundColor: isSelected
              ? Colors.blue.shade700
              : Colors.grey.shade700,
          minimumSize: const Size(double.infinity, 40),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        child: Text(label),
      ),
    );
  }
}
