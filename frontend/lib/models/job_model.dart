// ignore_for_file: constant_identifier_names

enum JobStatus {
  UPLOADED,
  DOWNLOADING,
  ANALYZING,
  EXTRACTING_AUDIO,
  TRANSCRIBING,
  TRANSLATING,
  GENERATING_TELUGU_AUDIO,
  SYNCHRONIZING,
  MIXING_AUDIO,
  RENDERING,
  VALIDATING,
  COMPLETED,
  FAILED;

  static JobStatus fromString(String val) {
    return JobStatus.values.firstWhere(
      (e) => e.name == val,
      orElse: () => JobStatus.UPLOADED,
    );
  }

  String get displayName {
    switch (this) {
      case JobStatus.UPLOADED:
        return 'Video Uploaded';
      case JobStatus.DOWNLOADING:
        return 'Downloading from YouTube';
      case JobStatus.ANALYZING:
        return 'Analyzing Video';
      case JobStatus.EXTRACTING_AUDIO:
        return 'Extracting Audio Track';
      case JobStatus.TRANSCRIBING:
        return 'Transcribing Hindi Speech';
      case JobStatus.TRANSLATING:
        return 'Translating to Telugu';
      case JobStatus.GENERATING_TELUGU_AUDIO:
        return 'Synthesizing Telugu Voice';
      case JobStatus.SYNCHRONIZING:
        return 'Synchronizing Audio Timings';
      case JobStatus.MIXING_AUDIO:
        return 'Mixing & Preserving Ambience';
      case JobStatus.RENDERING:
        return 'Rendering Final Video';
      case JobStatus.VALIDATING:
        return 'Quality Validation';
      case JobStatus.COMPLETED:
        return 'Dubbing Completed';
      case JobStatus.FAILED:
        return 'Processing Failed';
    }
  }
}

class SpeechSegment {
  final int segmentId;
  final double start;
  final double end;
  final double duration;
  final String hindiText;
  final String teluguText;
  final String? speaker;
  final double? confidence;
  final double? speedRatio;

  SpeechSegment({
    required this.segmentId,
    required this.start,
    required this.end,
    required this.duration,
    required this.hindiText,
    required this.teluguText,
    this.speaker,
    this.confidence,
    this.speedRatio,
  });

  factory SpeechSegment.fromJson(Map<String, dynamic> json) {
    return SpeechSegment(
      segmentId: json['segment_id'] ?? 0,
      start: (json['start'] as num?)?.toDouble() ?? 0.0,
      end: (json['end'] as num?)?.toDouble() ?? 0.0,
      duration: (json['duration'] as num?)?.toDouble() ?? 0.0,
      hindiText: json['hindi_text'] ?? '',
      teluguText: json['telugu_text'] ?? '',
      speaker: json['speaker'],
      confidence: (json['confidence'] as num?)?.toDouble(),
      speedRatio: (json['speed_ratio'] as num?)?.toDouble(),
    );
  }

  String get formattedStart => _formatTime(start);
  String get formattedEnd => _formatTime(end);

  static String _formatTime(double seconds) {
    final m = (seconds / 60).floor();
    final s = (seconds % 60).floor();
    final ms = ((seconds % 1) * 100).floor();
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}.${ms.toString().padLeft(2, '0')}';
  }
}

class MediaMetadata {
  final String filename;
  final double fileSizeMb;
  final double duration;
  final String resolution;
  final String videoCodec;
  final String? audioCodec;
  final bool hasAudio;
  final double? fps;

  MediaMetadata({
    required this.filename,
    required this.fileSizeMb,
    required this.duration,
    required this.resolution,
    required this.videoCodec,
    this.audioCodec,
    required this.hasAudio,
    this.fps,
  });

  factory MediaMetadata.fromJson(Map<String, dynamic> json) {
    return MediaMetadata(
      filename: json['filename'] ?? '',
      fileSizeMb: (json['file_size_mb'] as num?)?.toDouble() ?? 0.0,
      duration: (json['duration'] as num?)?.toDouble() ?? 0.0,
      resolution: json['resolution'] ?? '',
      videoCodec: json['video_codec'] ?? '',
      audioCodec: json['audio_codec'],
      hasAudio: json['has_audio'] ?? true,
      fps: (json['fps'] as num?)?.toDouble(),
    );
  }
}

class JobSettings {
  final String sourceLanguage;
  final String targetLanguage;
  final String voiceId;
  final double speakingRate;
  final bool preserveBackground;
  final double duckingDb;

  JobSettings({
    this.sourceLanguage = 'hi',
    this.targetLanguage = 'te',
    this.voiceId = 'te-IN-MohanNeural',
    this.speakingRate = 1.0,
    this.preserveBackground = true,
    this.duckingDb = -12.0,
  });

  factory JobSettings.fromJson(Map<String, dynamic> json) {
    return JobSettings(
      sourceLanguage: json['source_language'] ?? 'hi',
      targetLanguage: json['target_language'] ?? 'te',
      voiceId: json['voice_id'] ?? 'te-IN-MohanNeural',
      speakingRate: (json['speaking_rate'] as num?)?.toDouble() ?? 1.0,
      preserveBackground: json['preserve_background'] ?? true,
      duckingDb: (json['ducking_db'] as num?)?.toDouble() ?? -12.0,
    );
  }
}

class DubbingJob {
  final String jobId;
  final JobStatus status;
  final int progress;
  final String message;
  final String originalFilename;
  final String createdAt;
  final String updatedAt;
  final MediaMetadata? mediaMetadata;
  final JobSettings settings;
  final List<SpeechSegment> segments;
  final String? errorMessage;
  final String? outputVideoUrl;
  final String? originalVideoUrl;
  final String? subtitlesSrtUrl;
  final String? subtitlesVttUrl;

  DubbingJob({
    required this.jobId,
    required this.status,
    required this.progress,
    required this.message,
    required this.originalFilename,
    required this.createdAt,
    required this.updatedAt,
    this.mediaMetadata,
    required this.settings,
    required this.segments,
    this.errorMessage,
    this.outputVideoUrl,
    this.originalVideoUrl,
    this.subtitlesSrtUrl,
    this.subtitlesVttUrl,
  });

  factory DubbingJob.fromJson(Map<String, dynamic> json) {
    return DubbingJob(
      jobId: json['job_id'] ?? '',
      status: JobStatus.fromString(json['status'] ?? 'UPLOADED'),
      progress: json['progress'] ?? 0,
      message: json['message'] ?? '',
      originalFilename: json['original_filename'] ?? '',
      createdAt: json['created_at'] ?? '',
      updatedAt: json['updated_at'] ?? '',
      mediaMetadata: json['media_metadata'] != null
          ? MediaMetadata.fromJson(json['media_metadata'])
          : null,
      settings: json['settings'] != null
          ? JobSettings.fromJson(json['settings'])
          : JobSettings(),
      segments: (json['segments'] as List<dynamic>?)
              ?.map((s) => SpeechSegment.fromJson(s))
              .toList() ??
          [],
      errorMessage: json['error_message'],
      outputVideoUrl: json['output_video_url'],
      originalVideoUrl: json['original_video_url'],
      subtitlesSrtUrl: json['subtitles_srt_url'],
      subtitlesVttUrl: json['subtitles_vtt_url'],
    );
  }
}

class VoiceOption {
  final String voiceId;
  final String name;
  final String language;
  final String gender;
  final String provider;
  final String sampleText;

  VoiceOption({
    required this.voiceId,
    required this.name,
    required this.language,
    required this.gender,
    required this.provider,
    this.sampleText = '',
  });

  factory VoiceOption.fromJson(Map<String, dynamic> json) {
    return VoiceOption(
      voiceId: json['voice_id'] ?? '',
      name: json['name'] ?? '',
      language: json['language'] ?? '',
      gender: json['gender'] ?? '',
      provider: json['provider'] ?? '',
      sampleText: json['sample_text'] ?? '',
    );
  }
}
