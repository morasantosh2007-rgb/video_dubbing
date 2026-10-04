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

  final ValueNotifier<double?> _seekNotifier = ValueNotifier<double?>(null);
  final ScrollController _lyricsScrollController = ScrollController();
  double _currentPlaybackPosition = 0.0;
  int _activeSegmentIndex = -1;
  bool _isContinuousTextView = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(() {
      if (mounted) setState(() {});
    });
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

  void _onPlaybackPositionChanged(double pos) {
    if (!mounted) return;
    _currentPlaybackPosition = pos;

    if (_job == null || _job!.segments.isEmpty || _isContinuousTextView) {
      return;
    }

    int newActive = -1;
    for (int i = 0; i < _job!.segments.length; i++) {
      final seg = _job!.segments[i];
      if (pos >= (seg.start - 0.1) && pos <= (seg.end + 0.35)) {
        newActive = i;
        break;
      }
    }

    if (newActive != _activeSegmentIndex) {
      setState(() {
        _activeSegmentIndex = newActive;
      });
      if (newActive >= 0 && _lyricsScrollController.hasClients) {
        final targetOffset = (newActive * 64.0) - 100.0;
        final safeOffset = targetOffset.clamp(
          0.0,
          _lyricsScrollController.position.maxScrollExtent,
        );
        _lyricsScrollController.animateTo(
          safeOffset,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOutCubic,
        );
      }
    }
  }

  void _seekToSegment(SpeechSegment seg) {
    _seekNotifier.value = seg.start;
    Future.delayed(const Duration(milliseconds: 100), () {
      if (mounted) _seekNotifier.value = null;
    });
  }

  void _copyFullTeluguTranscript(DubbingJob job) {
    final fullText = job.segments
        .map((s) => s.teluguText.trim())
        .where((t) => t.isNotEmpty)
        .join(' ');
    Clipboard.setData(ClipboardData(text: fullText));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Full Telugu transcript copied to clipboard!'),
        backgroundColor: AppTheme.accent,
      ),
    );
  }

  Future<void> _confirmDeleteCurrentJob() async {
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
            Text('Delete Video Project', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Are you sure you want to permanently delete this project?',
              style: TextStyle(fontSize: 14, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 10),
            if (_job != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceElevated,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _job!.originalFilename,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            const SizedBox(height: 10),
            const Text(
              'This removes the dubbed video, subtitles, and server cache permanently.',
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
      final success = await ApiService.deleteJob(widget.jobId);
      if (mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Project deleted successfully'), backgroundColor: AppTheme.accent),
          );
          Navigator.pop(context);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to delete project'), backgroundColor: Colors.redAccent),
          );
        }
      }
    }
  }

  Future<void> _downloadVideo({bool withSubtitles = true}) async {
    final url = Uri.parse(ApiService.getDownloadUrl(widget.jobId, burnedSubtitles: withSubtitles));
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

  Future<void> _downloadSubtitles(String format) async {
    final downloadUrl = format == 'srt'
        ? ApiService.getSrtDownloadUrl(widget.jobId)
        : ApiService.getVttUrl(widget.jobId);
    final uri = Uri.parse(downloadUrl);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not trigger $format subtitle download.')),
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
    _seekNotifier.dispose();
    _lyricsScrollController.dispose();
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
          IconButton(
            icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
            tooltip: 'Delete Video Project',
            onPressed: _confirmDeleteCurrentJob,
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
                          height: 480,
                          child: TabBarView(
                            controller: _tabController,
                            children: [
                              VideoPlayerView(
                                videoUrl: dubbedUrl,
                                title: 'Telugu Dubbed Video',
                                isActive: _tabController.index == 0,
                                segments: job.segments,
                                isTelugu: true,
                                onPositionChanged: _onPlaybackPositionChanged,
                                seekNotifier: _seekNotifier,
                              ),
                              VideoPlayerView(
                                videoUrl: origUrl,
                                title: 'Original Hindi Video',
                                isActive: _tabController.index == 1,
                                segments: job.segments,
                                isTelugu: false,
                                onPositionChanged: _onPlaybackPositionChanged,
                                seekNotifier: _seekNotifier,
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
                              onPressed: () => _downloadVideo(withSubtitles: true),
                              icon: const Icon(Icons.subtitles),
                              label: const Text('Download with Subtitles (.mp4)'),
                              style: ElevatedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 16),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: () => _downloadVideo(withSubtitles: false),
                              icon: const Icon(Icons.download),
                              label: const Text('Download Clean Video (.mp4)'),
                              style: OutlinedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 16),
                                side: const BorderSide(color: AppTheme.border),
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
                            label: const Text('Dub Another'),
                            style: OutlinedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: () => _downloadSubtitles('srt'),
                              icon: const Icon(Icons.subtitles_outlined, color: AppTheme.primaryLight, size: 20),
                              label: const Text('Download Telugu Subtitles (.SRT)', style: TextStyle(fontSize: 13)),
                              style: OutlinedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 14),
                                side: const BorderSide(color: AppTheme.border),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: () => _downloadSubtitles('vtt'),
                              icon: const Icon(Icons.closed_caption_outlined, color: AppTheme.primaryLight, size: 20),
                              label: const Text('Download WebVTT (.VTT)', style: TextStyle(fontSize: 13)),
                              style: OutlinedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 14),
                                side: const BorderSide(color: AppTheme.border),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),

                // Unified Spotify-Style Telugu Lyrics & Dubbed Words Block
                _buildTeluguLyricsCard(job),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTeluguLyricsCard(DubbingJob job) {
    final fullTeluguText = job.segments
        .map((s) => s.teluguText.trim())
        .where((t) => t.isNotEmpty)
        .join(' ');

    final wordCount = fullTeluguText.isEmpty ? 0 : fullTeluguText.split(RegExp(r'\s+')).length;

    return Container(
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
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.lyrics_rounded, color: AppTheme.primaryLight, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    Text(
                      'Telugu Dubbed Words',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                    ),
                    SizedBox(height: 2),
                    Text(
                      'Live synced with video playback • Tap any line to seek video',
                      style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
              // View Mode Toggle (Live Lyrics vs Full Text Block)
              Tooltip(
                message: _isContinuousTextView ? 'Switch to Live Synced Lyrics' : 'Switch to Full Text View',
                child: IconButton(
                  icon: Icon(
                    _isContinuousTextView ? Icons.queue_music_rounded : Icons.article_outlined,
                    color: AppTheme.primaryLight,
                    size: 22,
                  ),
                  onPressed: () {
                    setState(() {
                      _isContinuousTextView = !_isContinuousTextView;
                    });
                  },
                ),
              ),
              // Quick Copy Button
              Tooltip(
                message: 'Copy All Telugu Words',
                child: IconButton(
                  icon: const Icon(Icons.copy_rounded, color: Colors.white70, size: 20),
                  onPressed: () => _copyFullTeluguTranscript(job),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          if (job.segments.isEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(28),
              decoration: BoxDecoration(
                color: AppTheme.surfaceElevated,
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Center(
                child: Text(
                  'No speech detected in this video.',
                  style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
                ),
              ),
            )
          else if (_isContinuousTextView)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: const Color(0xFF0F141C),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SelectableText(
                    fullTeluguText,
                    style: const TextStyle(
                      fontSize: 16,
                      height: 1.85,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                      letterSpacing: 0.3,
                    ),
                  ),
                  const SizedBox(height: 18),
                  const Divider(color: AppTheme.border),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _buildPill(Icons.timelapse, '${job.mediaMetadata?.duration ?? 0}s duration'),
                      _buildPill(Icons.text_fields, '$wordCount Telugu words'),
                      _buildPill(Icons.record_voice_over, '${job.segments.length} spoken segments'),
                    ],
                  ),
                ],
              ),
            )
          else
            Container(
              height: 380,
              decoration: BoxDecoration(
                color: const Color(0xFF0D1117),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: ListView.builder(
                  controller: _lyricsScrollController,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
                  itemCount: job.segments.length,
                  itemBuilder: (context, idx) {
                    final seg = job.segments[idx];
                    final isActive = idx == _activeSegmentIndex;
                    final isPast = !isActive && (_currentPlaybackPosition > seg.end + 0.35);

                    return InkWell(
                      onTap: () => _seekToSegment(seg),
                      borderRadius: BorderRadius.circular(12),
                      hoverColor: Colors.white.withOpacity(0.06),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 220),
                        margin: const EdgeInsets.symmetric(vertical: 3),
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        decoration: BoxDecoration(
                          color: isActive ? const Color(0xFF6366F1).withOpacity(0.18) : Colors.transparent,
                          borderRadius: BorderRadius.circular(12),
                          border: isActive
                              ? Border.all(color: const Color(0xFF818CF8).withOpacity(0.4), width: 1)
                              : null,
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            AnimatedContainer(
                              duration: const Duration(milliseconds: 180),
                              width: 4,
                              height: isActive ? 28 : 0,
                              decoration: BoxDecoration(
                                color: const Color(0xFF818CF8),
                                borderRadius: BorderRadius.circular(2),
                                boxShadow: isActive
                                    ? [
                                        const BoxShadow(
                                          color: Color(0xFF6366F1),
                                          blurRadius: 8,
                                          spreadRadius: 1,
                                        ),
                                      ]
                                    : null,
                              ),
                            ),
                            SizedBox(width: isActive ? 12 : 4),
                            Expanded(
                              child: Text(
                                seg.teluguText,
                                style: TextStyle(
                                  fontSize: isActive ? 19 : 15,
                                  fontWeight: isActive ? FontWeight.w800 : (isPast ? FontWeight.w500 : FontWeight.w400),
                                  color: isActive
                                      ? Colors.white
                                      : (isPast ? Colors.white60 : Colors.white30),
                                  height: 1.45,
                                  letterSpacing: 0.2,
                                ),
                              ),
                            ),
                            if (isActive) ...[
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF6366F1).withOpacity(0.25),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: const [
                                    Icon(Icons.graphic_eq_rounded, size: 14, color: Color(0xFF818CF8)),
                                    SizedBox(width: 4),
                                    Text(
                                      'PLAYING',
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                        color: Color(0xFF818CF8),
                                        letterSpacing: 0.5,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildPill(IconData icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppTheme.surfaceElevated,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: AppTheme.primaryLight),
          const SizedBox(width: 6),
          Text(text, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
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
