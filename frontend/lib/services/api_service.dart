import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/job_model.dart';

class ApiService {
  // Default development URL; can be dynamically overridden or set via environment
  static String baseUrl = kIsWeb
      ? 'http://127.0.0.1:8000'
      : (defaultTargetPlatform == TargetPlatform.android
          ? 'http://10.0.2.2:8000'
          : 'http://127.0.0.1:8000');

  static String get apiPrefix => '$baseUrl/api';

  static Future<bool> checkHealth() async {
    try {
      final res = await http.get(Uri.parse('$apiPrefix/health')).timeout(const Duration(seconds: 4));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  static Future<List<VoiceOption>> getVoices({String language = 'te'}) async {
    try {
      final res = await http.get(Uri.parse('$apiPrefix/voices?language=$language'));
      if (res.statusCode == 200) {
        final List<dynamic> data = jsonDecode(utf8.decode(res.bodyBytes));
        return data.map((v) => VoiceOption.fromJson(v)).toList();
      }
    } catch (e) {
      debugPrint('Error loading voices: $e');
    }
    return [
      VoiceOption(
        voiceId: 'te-IN-MohanNeural',
        name: 'Mohan (Natural Male)',
        language: 'te',
        gender: 'Male',
        provider: 'edge-tts',
      ),
      VoiceOption(
        voiceId: 'te-IN-ShrutiNeural',
        name: 'Shruti (Natural Female)',
        language: 'te',
        gender: 'Female',
        provider: 'edge-tts',
      ),
    ];
  }

  static Future<DubbingJob> uploadVideo({
    required Uint8List fileBytes,
    required String filename,
    required JobSettings settings,
  }) async {
    final uri = Uri.parse('$apiPrefix/jobs');
    final req = http.MultipartRequest('POST', uri);

    req.files.add(
      http.MultipartFile.fromBytes(
        'file',
        fileBytes,
        filename: filename,
      ),
    );

    req.fields['source_language'] = settings.sourceLanguage;
    req.fields['target_language'] = settings.targetLanguage;
    req.fields['voice_id'] = settings.voiceId;
    req.fields['speaking_rate'] = settings.speakingRate.toString();
    req.fields['preserve_background'] = settings.preserveBackground.toString();
    req.fields['ducking_db'] = settings.duckingDb.toString();

    final streamedRes = await req.send();
    final res = await http.Response.fromStream(streamedRes);

    if (res.statusCode == 201 || res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      return DubbingJob.fromJson(data);
    } else {
      String err = 'Upload failed (${res.statusCode})';
      try {
        final errJson = jsonDecode(utf8.decode(res.bodyBytes));
        if (errJson['detail'] != null) err = errJson['detail'];
      } catch (_) {}
      throw Exception(err);
    }
  }

  static Future<DubbingJob> getJob(String jobId) async {
    final res = await http.get(Uri.parse('$apiPrefix/jobs/$jobId'));
    if (res.statusCode == 200) {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      return DubbingJob.fromJson(data);
    }
    throw Exception('Failed to load job: ${res.statusCode}');
  }

  static Future<List<DubbingJob>> getRecentJobs() async {
    try {
      final res = await http.get(Uri.parse('$apiPrefix/jobs?limit=10'));
      if (res.statusCode == 200) {
        final List<dynamic> data = jsonDecode(utf8.decode(res.bodyBytes));
        return data.map((j) => DubbingJob.fromJson(j)).toList();
      }
    } catch (e) {
      debugPrint('Error getting recent jobs: $e');
    }
    return [];
  }

  static String getDubbedVideoUrl(String jobId, {bool burnedSubtitles = false}) =>
      burnedSubtitles ? '$apiPrefix/jobs/$jobId/video/subtitled' : '$apiPrefix/jobs/$jobId/video/dubbed';
  static String getSubtitledVideoUrl(String jobId) => '$apiPrefix/jobs/$jobId/video/subtitled';
  static String getOriginalVideoUrl(String jobId) => '$apiPrefix/jobs/$jobId/video/original';
  static String getDownloadUrl(String jobId, {bool burnedSubtitles = false}) =>
      burnedSubtitles ? '$apiPrefix/jobs/$jobId/download/subtitled' : '$apiPrefix/jobs/$jobId/download';
  static String getSubtitledDownloadUrl(String jobId) => '$apiPrefix/jobs/$jobId/download/subtitled';
  static String getSrtDownloadUrl(String jobId) => '$apiPrefix/jobs/$jobId/subtitles/srt';
  static String getVttUrl(String jobId) => '$apiPrefix/jobs/$jobId/subtitles/vtt';
}
