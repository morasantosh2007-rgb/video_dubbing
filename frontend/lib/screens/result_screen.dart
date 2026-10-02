import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/job_model.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/video_player_view.dart';
import 'upload_screen.dart';

class ResultScreen extends StatefulWidget {
  final String jobId;

  const ResultScreen({super.key, required this.jobId});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  DubbingJob? _job;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadJob();
  }

  Future<void> _loadJob() async {
    try {
      final job = await ApiService.getJob(widget.jobId);
      if (mounted) {
        setState(() {
          _job = job;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _downloadVideo() async {
    final url = Uri.parse(ApiService.getDownloadUrl(widget.jobId));
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not trigger automatic download. Use copy link.')),
        );
      }
    }
  }

  void _copyDownloadLink() {
    final link = ApiService.getDownloadUrl(widget.jobId);
    Clipboard.setData(ClipboardData(text: link));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Dubbed video link copied to clipboard!'),
        backgroundColor: AppTheme.accent,
      ),
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (_errorMessage != null || _job == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Job Result')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.redAccent),
              const SizedBox(height: 12),
              Text('Error: $_errorMessage'),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Go Back'),
              ),
            ],
          ),
        ),
      );
    }

    final job = _job!;
    final dubbedUrl = ApiService.getDubbedVideoUrl(job.jobId);
    final origUrl = ApiService.getOriginalVideoUrl(job.jobId);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Telugu Dubbing Result'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined),
            tooltip: 'Copy Video Link',
            onPressed: _copyDownloadLink,
          ),
          IconButton(
            icon: const Icon(Icons.download_rounded),
            tooltip: 'Download Dubbed Video',
            onPressed: _downloadVideo,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 880),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header Banner
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF065F46), Color(0xFF064E3B)],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.accent.withOpacity(0.5)),
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: const BoxDecoration(
                          color: Colors.white24,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.check, color: Colors.white, size: 24),
                      ),
                      const SizedBox(width: 16),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Dubbing Completed Successfully!',
                              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                            ),
                            SizedBox(height: 4),
                            Text(
                              'Original visuals 100% preserved. Hindi speech replaced with synchronized Telugu audio.',
                              style: TextStyle(fontSize: 13, color: Colors.white70),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // Video Preview with Before / After Tabs
                Container(
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    children: [
                      TabBar(
                        controller: _tabController,
                        indicatorColor: AppTheme.primary,
                        labelColor: Colors.white,
                        unselectedLabelColor: AppTheme.textSecondary,
                        tabs: const [
                          Tab(
                            icon: Icon(Icons.auto_awesome),
                            text: 'Dubbed Video (Telugu)',
                          ),
                          Tab(
                            icon: Icon(Icons.movie_outlined),
                            text: 'Original Video (Hindi)',
                          ),
                        ],
                      ),
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: SizedBox(
                          height: 400,
                          child: TabBarView(
                            controller: _tabController,
                            children: [
                              VideoPlayerView(
                                videoUrl: dubbedUrl,
                                title: 'Telugu Dubbed Video',
                              ),
                              VideoPlayerView(
                                videoUrl: origUrl,
                                title: 'Original Hindi Video',
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // Video Summary & Action Buttons Card
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceAround,
                        children: [
                          _buildStatColumn('Duration', '${job.mediaMetadata?.duration ?? 0}s'),
                          _buildStatColumn('Resolution', job.mediaMetadata?.resolution ?? 'Original'),
                          _buildStatColumn('Segments', '${job.segments.length} spoken'),
                          _buildStatColumn('Target Voice', job.settings.voiceId.contains('Mohan') ? 'Mohan (M)' : 'Shruti (F)'),
                        ],
                      ),
                      const Divider(height: 36, color: AppTheme.border),
                      Row(
                        children: [
                          Expanded(
                            child: ElevatedButton.icon(
                              onPressed: _downloadVideo,
                              icon: const Icon(Icons.download),
                              label: const Text('Download Telugu Video'),
                              style: ElevatedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 16),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          OutlinedButton.icon(
                            onPressed: () {
                              Navigator.pushReplacement(
                                context,
                                MaterialPageRoute(builder: (context) => const UploadScreen()),
                              );
                            },
                            icon: const Icon(Icons.add),
                            label: const Text('Dub Another Video'),
                            style: OutlinedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),

                // Speech Segment Breakdown Table
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
                        'Timestamped Speech Segment Alignment',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        'Detailed breakdown of Hindi transcription, Telugu translation, and synchronized interval timing.',
                        style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                      ),
                      const SizedBox(height: 20),
                      if (job.segments.isEmpty)
                        const Text('No speech segments found.')
                      else
                        ListView.separated(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: job.segments.length,
                          separatorBuilder: (context, _) => const Divider(color: AppTheme.border, height: 24),
                          itemBuilder: (context, idx) {
                            final seg = job.segments[idx];
                            return Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                      decoration: BoxDecoration(
                                        color: AppTheme.surfaceElevated,
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Text(
                                        '#${seg.segmentId}  ${seg.formattedStart} → ${seg.formattedEnd} (${seg.duration}s)',
                                        style: const TextStyle(
                                          fontSize: 12,
                                          fontWeight: FontWeight.bold,
                                          color: AppTheme.primaryLight,
                                        ),
                                      ),
                                    ),
                                    if (seg.speedRatio != null) ...[
                                      const SizedBox(width: 8),
                                      Text(
                                        'Speed Ratio: ${seg.speedRatio!.toStringAsFixed(2)}x',
                                        style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                                      ),
                                    ],
                                  ],
                                ),
                                const SizedBox(height: 10),
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text('Hindi: ', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.amberAccent)),
                                    Expanded(
                                      child: Text(
                                        seg.hindiText,
                                        style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text('Telugu: ', style: TextStyle(fontWeight: FontWeight.bold, color: AppTheme.accent)),
                                    Expanded(
                                      child: Text(
                                        seg.teluguText,
                                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Colors.white),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            );
                          },
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStatColumn(String label, String value) {
    return Column(
      children: [
        Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white)),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
      ],
    );
  }
}
