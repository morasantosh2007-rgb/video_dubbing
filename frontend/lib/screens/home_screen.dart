import 'package:flutter/material.dart';
import '../models/job_model.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'upload_screen.dart';
import 'result_screen.dart';
import 'processing_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _backendOnline = false;
  bool _isLoadingRecent = true;
  List<DubbingJob> _recentJobs = [];

  @override
  void initState() {
    super.initState();
    _checkStatusAndLoadJobs();
  }

  Future<void> _checkStatusAndLoadJobs() async {
    setState(() => _isLoadingRecent = true);
    final online = await ApiService.checkHealth();
    List<DubbingJob> jobs = [];
    if (online) {
      jobs = await ApiService.getRecentJobs();
    }
    if (mounted) {
      setState(() {
        _backendOnline = online;
        _recentJobs = jobs;
        _isLoadingRecent = false;
      });
    }
  }

  Future<void> _confirmDeleteJob(DubbingJob job) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppTheme.border),
        ),
        title: const Row(
          children: [
            Icon(Icons.delete_outline, color: Colors.redAccent, size: 24),
            SizedBox(width: 10),
            Text(
              'Delete Project',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Are you sure you want to delete this project?',
              style: TextStyle(fontSize: 14, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.surfaceElevated,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                job.originalFilename,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(height: 10),
            const Text(
              'This will permanently remove the video, audio, and subtitle files from the server.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: AppTheme.textSecondary)),
          ),
          ElevatedButton.icon(
            onPressed: () => Navigator.pop(ctx, true),
            icon: const Icon(Icons.delete_forever, size: 18),
            label: const Text('Delete'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.redAccent,
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final success = await ApiService.deleteJob(job.jobId);
      if (mounted) {
        if (success) {
          setState(() {
            _recentJobs.removeWhere((j) => j.jobId == job.jobId);
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Project deleted successfully'),
              backgroundColor: AppTheme.accent,
              duration: Duration(seconds: 3),
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Failed to delete project'),
              backgroundColor: Colors.redAccent,
            ),
          );
        }
      }
    }
  }


  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppTheme.primary, AppTheme.primaryLight],
                ),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.record_voice_over, color: Colors.white, size: 20),
            ),
            const SizedBox(width: 12),
            const Text(
              'DubAI',
              style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: -0.5),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _backendOnline
                      ? AppTheme.accent.withOpacity(0.15)
                      : Colors.redAccent.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: _backendOnline ? AppTheme.accent : Colors.redAccent,
                    width: 1,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CircleAvatar(
                      radius: 4,
                      backgroundColor: _backendOnline ? AppTheme.accent : Colors.redAccent,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      _backendOnline ? 'Backend Online' : 'Connecting...',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: _backendOnline ? AppTheme.accent : Colors.redAccent,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _checkStatusAndLoadJobs,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 960),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Hero Card
                  _buildHeroSection(),
                  const SizedBox(height: 36),

                  // Feature Cards
                  _buildFeatureHighlights(),
                  const SizedBox(height: 40),

                  // Recent Projects
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Recent Projects',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.refresh, size: 20, color: AppTheme.textSecondary),
                        onPressed: _checkStatusAndLoadJobs,
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _buildRecentJobsList(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeroSection() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF1E1B4B), // Deep indigo
            AppTheme.surface,
          ],
        ),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppTheme.primary.withOpacity(0.3), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primary.withOpacity(0.12),
            blurRadius: 32,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppTheme.primary.withOpacity(0.2),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppTheme.primaryLight.withOpacity(0.4)),
            ),
            child: const Text(
              'Hindi → Telugu AI Video Dubbing',
              style: TextStyle(
                color: AppTheme.primaryLight,
                fontSize: 13,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(height: 20),
          const Text(
            'Dub Hindi Videos into Natural Telugu\nWith Perfect Audio Sync',
            style: TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w900,
              color: Colors.white,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 14),
          const Text(
            'Keep 100% of the original video stream, frames, resolution, and background audio while replacing Hindi dialogue with natural neural Telugu voice synthesis.',
            style: TextStyle(
              fontSize: 16,
              color: AppTheme.textSecondary,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 28),
          ElevatedButton.icon(
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const UploadScreen()),
              ).then((_) => _checkStatusAndLoadJobs());
            },
            icon: const Icon(Icons.upload_file),
            label: const Text('Upload Video to Dub'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 18),
              textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureHighlights() {
    final features = [
      {
        'icon': Icons.movie_creation_outlined,
        'title': 'Original Video Preserved',
        'desc': 'No re-encoding artifacts. Stream copied directly via FFmpeg.'
      },
      {
        'icon': Icons.sync,
        'title': 'Timestamp Synchronization',
        'desc': 'Time-stretching with pitch preservation matches speech timing intervals.'
      },
      {
        'icon': Icons.surround_sound,
        'title': 'Background Ambience',
        'desc': 'Dynamic sidechain ducking keeps music, sound effects, and room tone intact.'
      },
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        final isWide = constraints.maxWidth > 650;
        if (isWide) {
          return Row(
            children: features.map((f) => Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6),
                child: _buildFeatureCard(f),
              ),
            )).toList(),
          );
        } else {
          return Column(
            children: features.map((f) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _buildFeatureCard(f),
            )).toList(),
          );
        }
      },
    );
  }

  Widget _buildFeatureCard(Map<String, dynamic> f) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.surfaceElevated,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(f['icon'] as IconData, color: AppTheme.primaryLight, size: 24),
          ),
          const SizedBox(height: 14),
          Text(
            f['title'] as String,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            f['desc'] as String,
            style: const TextStyle(
              fontSize: 13,
              color: AppTheme.textSecondary,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecentJobsList() {
    if (_isLoadingRecent) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: CircularProgressIndicator(),
        ),
      );
    }

    if (_recentJobs.isEmpty) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppTheme.border),
        ),
        child: Column(
          children: [
            Icon(Icons.video_library_outlined, size: 48, color: AppTheme.textSecondary.withOpacity(0.5)),
            const SizedBox(height: 12),
            const Text(
              'No dubbing jobs yet',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 4),
            const Text(
              'Upload a Hindi video to get started with instant AI Telugu dubbing.',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
            ),
          ],
        ),
      );
    }

    return Column(
      children: _recentJobs.map((job) {
        final isDone = job.status == JobStatus.COMPLETED;
        final isFailed = job.status == JobStatus.FAILED;

        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            leading: CircleAvatar(
              backgroundColor: isDone
                  ? AppTheme.accent.withOpacity(0.2)
                  : (isFailed ? Colors.redAccent.withOpacity(0.2) : AppTheme.primary.withOpacity(0.2)),
              child: Icon(
                isDone
                    ? Icons.check
                    : (isFailed ? Icons.error_outline : Icons.autorenew),
                color: isDone
                    ? AppTheme.accent
                    : (isFailed ? Colors.redAccent : AppTheme.primaryLight),
              ),
            ),
            title: Text(
              job.originalFilename,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
            ),
            subtitle: Text(
              '${job.status.displayName} • ${job.progress}%',
              style: TextStyle(
                fontSize: 12,
                color: isDone ? AppTheme.accent : AppTheme.textSecondary,
              ),
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 20, color: Colors.white54),
                  tooltip: 'Delete project',
                  hoverColor: Colors.redAccent.withOpacity(0.18),
                  splashRadius: 20,
                  onPressed: () => _confirmDeleteJob(job),
                ),
                const SizedBox(width: 4),
                const Icon(Icons.chevron_right, color: AppTheme.textSecondary, size: 20),
              ],
            ),
            onTap: () {
              if (job.status == JobStatus.COMPLETED) {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => ResultScreen(jobId: job.jobId)),
                );
              } else {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => ProcessingScreen(jobId: job.jobId)),
                );
              }
            },
          ),
        );
      }).toList(),
    );
  }
}
