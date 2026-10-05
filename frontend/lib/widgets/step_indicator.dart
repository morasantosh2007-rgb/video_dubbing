import 'package:flutter/material.dart';
import '../models/job_model.dart';
import '../theme/app_theme.dart';

class StepIndicator extends StatelessWidget {
  final JobStatus currentStatus;
  final int progress;

  const StepIndicator({
    super.key,
    required this.currentStatus,
    required this.progress,
  });

  static const List<Map<String, dynamic>> _steps = [
    {'status': JobStatus.UPLOADED, 'title': 'Video Sourced / Downloaded'},
    {'status': JobStatus.ANALYZING, 'title': 'Media Analyzed'},
    {'status': JobStatus.EXTRACTING_AUDIO, 'title': 'Audio Extracted'},
    {'status': JobStatus.TRANSCRIBING, 'title': 'Hindi Speech Transcribed'},
    {'status': JobStatus.TRANSLATING, 'title': 'Telugu Translation Generated'},
    {'status': JobStatus.GENERATING_TELUGU_AUDIO, 'title': 'Telugu Voice Synthesized'},
    {'status': JobStatus.SYNCHRONIZING, 'title': 'Audio Timings Synchronized'},
    {'status': JobStatus.MIXING_AUDIO, 'title': 'Background Audio Ducked & Mixed'},
    {'status': JobStatus.RENDERING, 'title': 'Video & Telugu Audio Muxed'},
    {'status': JobStatus.VALIDATING, 'title': 'Media Quality Verified'},
  ];

  int get _currentIndex {
    if (currentStatus == JobStatus.DOWNLOADING) return 0;
    for (int i = 0; i < _steps.length; i++) {
      if (_steps[i]['status'] == currentStatus) return i;
    }
    if (currentStatus == JobStatus.COMPLETED) return _steps.length;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final activeIndex = _currentIndex;

    return Column(
      children: List.generate(_steps.length, (index) {
        final step = _steps[index];
        final isDone = activeIndex > index || currentStatus == JobStatus.COMPLETED;
        final isCurrent = activeIndex == index && currentStatus != JobStatus.COMPLETED && currentStatus != JobStatus.FAILED;
        final isFailed = currentStatus == JobStatus.FAILED && activeIndex == index;

        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 6.0),
          child: Row(
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isDone
                      ? AppTheme.accent
                      : (isCurrent
                          ? AppTheme.primary
                          : (isFailed ? Colors.redAccent : AppTheme.surfaceElevated)),
                  border: Border.all(
                    color: isCurrent
                        ? AppTheme.primaryLight
                        : (isDone ? AppTheme.accent : AppTheme.border),
                    width: 2,
                  ),
                ),
                child: Center(
                  child: isDone
                      ? const Icon(Icons.check, size: 16, color: Colors.white)
                      : (isCurrent
                          ? const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : (isFailed
                              ? const Icon(Icons.close, size: 16, color: Colors.white)
                              : Text(
                                  '${index + 1}',
                                  style: const TextStyle(
                                    fontSize: 11,
                                    color: AppTheme.textSecondary,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ))),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  step['title'] as String,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: isCurrent ? FontWeight.bold : FontWeight.w500,
                    color: isCurrent
                        ? AppTheme.textPrimary
                        : (isDone
                            ? AppTheme.textPrimary
                            : AppTheme.textSecondary.withOpacity(0.6)),
                  ),
                ),
              ),
              if (isDone)
                const Icon(Icons.check_circle_outline, color: AppTheme.accent, size: 18)
              else if (isCurrent)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Text(
                    'Active',
                    style: TextStyle(fontSize: 11, color: AppTheme.primaryLight, fontWeight: FontWeight.bold),
                  ),
                ),
            ],
          ),
        );
      }),
    );
  }
}
