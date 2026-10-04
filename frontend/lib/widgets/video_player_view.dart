import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../models/job_model.dart';

class VideoPlayerView extends StatefulWidget {
  final String videoUrl;
  final String title;
  final bool isActive;
  final List<SpeechSegment>? segments;
  final bool isTelugu;

  const VideoPlayerView({
    super.key,
    required this.videoUrl,
    required this.title,
    this.isActive = true,
    this.segments,
    this.isTelugu = true,
  });

  @override
  State<VideoPlayerView> createState() => _VideoPlayerViewState();
}

class _VideoPlayerViewState extends State<VideoPlayerView> {
  late VideoPlayerController _controller;
  bool _isInitialized = false;
  bool _hasError = false;
  String _errorText = '';
  bool _subtitlesEnabled = true;
  String _currentSubtitle = '';

  @override
  void initState() {
    super.initState();
    _initPlayer();
  }

  void _onControllerUpdate() {
    if (!mounted || !_isInitialized) return;
    if (widget.segments == null || widget.segments!.isEmpty) {
      if (_currentSubtitle.isNotEmpty) {
        setState(() => _currentSubtitle = '');
      }
      return;
    }

    final pos = _controller.value.position.inMilliseconds / 1000.0;
    String matched = '';
    for (final seg in widget.segments!) {
      if (pos >= seg.start && pos <= (seg.end + 0.25)) {
        matched = widget.isTelugu ? seg.teluguText : seg.hindiText;
        break;
      }
    }

    if (matched != _currentSubtitle) {
      setState(() {
        _currentSubtitle = matched;
      });
    }
  }

  void _initPlayer() async {
    try {
      _controller = VideoPlayerController.networkUrl(Uri.parse(widget.videoUrl));
      await _controller.initialize();
      _controller.setLooping(false);
      _controller.addListener(_onControllerUpdate);
      if (mounted) {
        setState(() {
          _isInitialized = true;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _hasError = true;
          _errorText = e.toString();
        });
      }
    }
  }

  @override
  void didUpdateWidget(covariant VideoPlayerView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.videoUrl != widget.videoUrl) {
      _controller.removeListener(_onControllerUpdate);
      _controller.dispose();
      setState(() {
        _isInitialized = false;
        _hasError = false;
        _currentSubtitle = '';
      });
      _initPlayer();
    } else if (oldWidget.isActive && !widget.isActive) {
      if (_isInitialized && _controller.value.isPlaying) {
        _controller.pause();
      }
    }
  }

  @override
  void dispose() {
    _controller.removeListener(_onControllerUpdate);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_hasError) {
      return Container(
        height: 240,
        decoration: BoxDecoration(
          color: Colors.black26,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.red.withOpacity(0.3)),
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, color: Colors.redAccent, size: 36),
              const SizedBox(height: 8),
              Text('Unable to play video: $_errorText',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 12, color: Colors.white70)),
            ],
          ),
        ),
      );
    }

    if (!_isInitialized) {
      return Container(
        height: 240,
        decoration: BoxDecoration(
          color: Colors.black38,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 12),
              Text('Loading video stream...', style: TextStyle(color: Colors.white70)),
            ],
          ),
        ),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: Container(
        color: Colors.black,
        child: Column(
          children: [
            AspectRatio(
              aspectRatio: _controller.value.aspectRatio > 0
                  ? _controller.value.aspectRatio
                  : 16 / 9,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  VideoPlayer(_controller),
                  GestureDetector(
                    onTap: () {
                      setState(() {
                        _controller.value.isPlaying
                            ? _controller.pause()
                            : _controller.play();
                      });
                    },
                    child: AnimatedOpacity(
                      opacity: _controller.value.isPlaying ? 0.0 : 0.85,
                      duration: const Duration(milliseconds: 200),
                      child: Container(
                        decoration: const BoxDecoration(
                          color: Colors.black45,
                          shape: BoxShape.circle,
                        ),
                        padding: const EdgeInsets.all(16),
                        child: Icon(
                          _controller.value.isPlaying
                              ? Icons.pause
                              : Icons.play_arrow,
                          size: 48,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                  if (_subtitlesEnabled && _currentSubtitle.isNotEmpty)
                    Positioned(
                      bottom: 16,
                      left: 16,
                      right: 16,
                      child: Center(
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.82),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.white24, width: 0.5),
                          ),
                          child: Text(
                            _currentSubtitle,
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              height: 1.35,
                              shadows: [
                                Shadow(blurRadius: 3.0, color: Colors.black, offset: Offset(1.0, 1.0)),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              color: const Color(0xFF131A29),
              child: Row(
                children: [
                  IconButton(
                    icon: Icon(
                      _controller.value.isPlaying ? Icons.pause : Icons.play_arrow,
                      color: Colors.white,
                    ),
                    onPressed: () {
                      setState(() {
                        _controller.value.isPlaying
                            ? _controller.pause()
                            : _controller.play();
                      });
                    },
                  ),
                  Expanded(
                    child: VideoProgressIndicator(
                      _controller,
                      allowScrubbing: true,
                      colors: const VideoProgressColors(
                        playedColor: Color(0xFF6366F1),
                        bufferedColor: Colors.white24,
                        backgroundColor: Colors.white10,
                      ),
                    ),
                  ),
                  if (widget.segments != null && widget.segments!.isNotEmpty) ...[
                    const SizedBox(width: 4),
                    IconButton(
                      icon: Icon(
                        _subtitlesEnabled ? Icons.closed_caption : Icons.closed_caption_disabled,
                        color: _subtitlesEnabled ? const Color(0xFF6366F1) : Colors.white38,
                        size: 22,
                      ),
                      tooltip: _subtitlesEnabled ? 'Hide Subtitles' : 'Show Subtitles',
                      onPressed: () {
                        setState(() {
                          _subtitlesEnabled = !_subtitlesEnabled;
                        });
                      },
                    ),
                  ],
                  const SizedBox(width: 6),
                  Text(
                    widget.title,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.white70,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
