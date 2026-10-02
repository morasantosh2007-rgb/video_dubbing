import 'dart:async';
import 'package:flutter/material.dart';
import '../models/job_model.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/step_indicator.dart';
import 'result_screen.dart';

class ProcessingScreen extends StatefulWidget {
  final String jobId;

  const ProcessingScreen({super.key, required this.jobId});

  @override
  State<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends State<ProcessingScreen> {
  Timer? _pollTimer;
  DubbingJob? _job;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _fetchJob();
    _startPolling();
  }

  void _startPolling() {
    _pollTimer = Timer.periodic(const Duration(milliseconds: 1500), (_) {
      _fetchJob();
    });
  }

  Future<void> _fetchJob() async {
    try {
      final job = await ApiService.getJob(widget.jobId);
      if (!mounted) return;

      setState(() {
        _job = job;
        _isLoading = false;
      });

      if (job.status == JobStatus.COMPLETED) {
        _pollTimer?.cancel();
        // Give 500ms to see 100% completion before transition
        Future.delayed(const Duration(milliseconds: 600), () {
          if (mounted) {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (context) => ResultScreen(jobId: widget.jobId)),
            );
          }
        });
      } else if (job.status == JobStatus.FAILED) {
        _pollTimer?.cancel();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceAll('Exception: ', '');
          _isLoading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_errorMessage != null && _job == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Error Connecting')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.redAccent),
              const SizedBox(height: 12),
              Text('Connection Error: $_errorMessage', textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  setState(() {
                    _isLoading = true;
                    _errorMessage = null;
                  });
                  _fetchJob();
                },
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_isLoading && _job == null) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Connecting to Dubbing Engine...'),
            ],
          ),
        ),
      );
    }

    final isFailed = _job?.status == JobStatus.FAILED;

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Dubbing Pipeline'),
        automaticallyImplyLeading: isFailed,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Main Progress Card
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: isFailed ? Colors.redAccent : AppTheme.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                isFailed ? 'Processing Encountered an Issue' : 'AI Dubbing in Progress',
                                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _job?.originalFilename ?? 'Video',
                                style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                              ),
                            ],
                          ),
                          Text(
                            '${_job?.progress ?? 0}%',
                            style: TextStyle(
                              fontSize: 28,
                              fontWeight: FontWeight.w900,
                              color: isFailed ? Colors.redAccent : AppTheme.primaryLight,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),

                      // Progress Bar
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: LinearProgressIndicator(
                          value: (_job?.progress ?? 0) / 100.0,
                          minHeight: 10,
                          backgroundColor: AppTheme.surfaceElevated,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            isFailed ? Colors.redAccent : AppTheme.primary,
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Live Status Message
                      Row(
                        children: [
                          if (!isFailed)
                            const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.accent),
                            )
                          else
                            const Icon(Icons.error, color: Colors.redAccent, size: 16),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              isFailed
                                  ? (_job?.errorMessage ?? 'An error occurred during processing.')
                                  : (_job?.message ?? 'Processing media...'),
                              style: TextStyle(
                                fontSize: 14,
                                color: isFailed ? Colors.redAccent : AppTheme.textPrimary,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),

                // Real Pipeline Steps Checklist
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Pipeline Execution Stages',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 16),
                      StepIndicator(
                        currentStatus: _job?.status ?? JobStatus.UPLOADED,
                        progress: _job?.progress ?? 0,
                      ),
                    ],
                  ),
                ),

                if (isFailed) ...[
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: ElevatedButton.icon(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.arrow_back),
                      label: const Text('Return to Upload'),
                      style: ElevatedButton.styleFrom(backgroundColor: AppTheme.surfaceElevated),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
