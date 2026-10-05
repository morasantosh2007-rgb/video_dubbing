import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import '../models/job_model.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'processing_screen.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  // Mode: 0 for File Upload, 1 for YouTube Link
  int _selectedTab = 0;

  // File Upload State
  Uint8List? _selectedFileBytes;
  String? _selectedFileName;
  double _fileSizeMb = 0.0;

  // YouTube Link State
  final TextEditingController _youtubeUrlController = TextEditingController();

  // Settings State
  List<VoiceOption> _voices = [];
  String _selectedVoiceId = 'te-IN-MohanNeural';
  double _speakingRate = 1.0;
  bool _preserveBackground = false;
  double _duckingDb = -12.0;

  bool _isUploading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadVoices();
  }

  @override
  void dispose() {
    _youtubeUrlController.dispose();
    super.dispose();
  }

  Future<void> _loadVoices() async {
    final v = await ApiService.getVoices(language: 'te');
    if (mounted) {
      setState(() {
        _voices = v;
        if (v.isNotEmpty) {
          _selectedVoiceId = v.first.voiceId;
        }
      });
    }
  }

  Future<void> _pickVideo() async {
    setState(() => _errorMessage = null);
    try {
      final file = await FilePicker.pickFile(
        type: FileType.custom,
        allowedExtensions: ['mp4', 'mov', 'mkv', 'webm'],
      );

      if (file != null) {
        final bytes = await file.readAsBytes();
        final size = (await file.length()) ?? bytes.length;
        setState(() {
          _selectedFileBytes = bytes;
          _selectedFileName = file.name;
          _fileSizeMb = size / (1024 * 1024);
        });
      }
    } catch (e) {
      setState(() => _errorMessage = 'Failed to pick video: $e');
    }
  }

  Future<void> _pasteFromClipboard() async {
    try {
      final data = await Clipboard.getData(Clipboard.kTextPlain);
      if (data?.text != null) {
        setState(() {
          _youtubeUrlController.text = data!.text!.trim();
          _errorMessage = null;
        });
      }
    } catch (e) {
      debugPrint('Error pasting from clipboard: $e');
    }
  }

  bool _isValidYoutubeUrl(String url) {
    final clean = url.trim();
    if (clean.isEmpty) return false;
    final regex = RegExp(
      r'^(https?:\/\/)?(www\.|m\.)?(youtube\.com\/(watch\?.*v=|shorts\/|embed\/)|youtu\.be\/)([\w-]{11})',
      caseSensitive: false,
    );
    return regex.hasMatch(clean);
  }

  Future<void> _startDubbing() async {
    final settings = JobSettings(
      sourceLanguage: 'hi',
      targetLanguage: 'te',
      voiceId: _selectedVoiceId,
      speakingRate: _speakingRate,
      preserveBackground: _preserveBackground,
      duckingDb: _duckingDb,
    );

    if (_selectedTab == 0) {
      // Local file mode
      if (_selectedFileBytes == null || _selectedFileName == null) {
        setState(() => _errorMessage = 'Please choose a video file first');
        return;
      }

      setState(() {
        _isUploading = true;
        _errorMessage = null;
      });

      try {
        final job = await ApiService.uploadVideo(
          fileBytes: _selectedFileBytes!,
          filename: _selectedFileName!,
          settings: settings,
        );

        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (context) => ProcessingScreen(jobId: job.jobId),
            ),
          );
        }
      } catch (e) {
        if (mounted) {
          setState(() {
            _isUploading = false;
            _errorMessage = e.toString().replaceAll('Exception: ', '');
          });
        }
      }
    } else {
      // YouTube Link mode
      final ytUrl = _youtubeUrlController.text.trim();
      if (ytUrl.isEmpty) {
        setState(() => _errorMessage = 'Please enter or paste a YouTube video URL');
        return;
      }
      if (!_isValidYoutubeUrl(ytUrl)) {
        setState(() => _errorMessage = 'Please enter a valid YouTube video or Shorts link');
        return;
      }

      setState(() {
        _isUploading = true;
        _errorMessage = null;
      });

      try {
        final job = await ApiService.submitYoutubeJob(
          youtubeUrl: ytUrl,
          settings: settings,
        );

        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (context) => ProcessingScreen(jobId: job.jobId),
            ),
          );
        }
      } catch (e) {
        if (mounted) {
          setState(() {
            _isUploading = false;
            _errorMessage = e.toString().replaceAll('Exception: ', '');
          });
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Configure Dubbing Job'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 800),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Source Selector Tab (Upload File vs YouTube Link)
                _buildSourceTabSelector(),
                const SizedBox(height: 20),

                // Active Source Input Area
                if (_selectedTab == 0)
                  _buildUploadDropzone()
                else
                  _buildYoutubeInputCard(),
                const SizedBox(height: 28),

                // Voice & Dubbing Settings
                _buildSettingsCard(),
                const SizedBox(height: 28),

                // Error Message
                if (_errorMessage != null)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    margin: const EdgeInsets.only(bottom: 24),
                    decoration: BoxDecoration(
                      color: Colors.redAccent.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: Colors.redAccent.withOpacity(0.4)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline, color: Colors.redAccent),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            _errorMessage!,
                            style: const TextStyle(color: Colors.redAccent, fontSize: 14),
                          ),
                        ),
                      ],
                    ),
                  ),

                // Submit Button
                SizedBox(
                  width: double.infinity,
                  height: 56,
                  child: ElevatedButton(
                    onPressed: _isUploading ? null : _startDubbing,
                    child: _isUploading
                        ? Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              ),
                              const SizedBox(width: 14),
                              Text(
                                _selectedTab == 0
                                    ? 'Uploading Video to Pipeline...'
                                    : 'Connecting to YouTube...',
                              ),
                            ],
                          )
                        : Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.auto_awesome),
                              const SizedBox(width: 10),
                              Text(
                                _selectedTab == 0
                                    ? 'Start Telugu Dubbing'
                                    : 'Extract & Dub YouTube Video',
                                style: const TextStyle(fontSize: 16),
                              ),
                            ],
                          ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSourceTabSelector() {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surfaceElevated,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: [
          Expanded(
            child: GestureDetector(
              onTap: () => setState(() {
                _selectedTab = 0;
                _errorMessage = null;
              }),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: _selectedTab == 0 ? AppTheme.primary : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.upload_file,
                      size: 18,
                      color: _selectedTab == 0 ? Colors.white : AppTheme.textSecondary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Upload File',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: _selectedTab == 0 ? Colors.white : AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Expanded(
            child: GestureDetector(
              onTap: () => setState(() {
                _selectedTab = 1;
                _errorMessage = null;
              }),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: _selectedTab == 1 ? AppTheme.primary : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.smart_display,
                      size: 18,
                      color: _selectedTab == 1 ? Colors.white : AppTheme.textSecondary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'YouTube Link',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: _selectedTab == 1 ? Colors.white : AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUploadDropzone() {
    final hasFile = _selectedFileName != null;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: hasFile ? AppTheme.primaryLight : AppTheme.border,
          width: hasFile ? 2 : 1,
        ),
      ),
      child: Column(
        children: [
          Icon(
            hasFile ? Icons.check_circle : Icons.cloud_upload_outlined,
            size: 56,
            color: hasFile ? AppTheme.accent : AppTheme.primaryLight,
          ),
          const SizedBox(height: 16),
          Text(
            hasFile ? _selectedFileName! : 'Select Hindi Video File',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          Text(
            hasFile
                ? 'Size: ${_fileSizeMb.toStringAsFixed(2)} MB • Ready to dub'
                : 'Supports MP4, MOV, MKV, WEBM (Up to 500 MB)',
            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: _pickVideo,
            icon: Icon(hasFile ? Icons.sync : Icons.folder_open),
            label: Text(hasFile ? 'Change Video' : 'Browse Files'),
          ),
        ],
      ),
    );
  }

  Widget _buildYoutubeInputCard() {
    final urlText = _youtubeUrlController.text.trim();
    final isValid = _isValidYoutubeUrl(urlText);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isValid ? Colors.greenAccent.withOpacity(0.6) : AppTheme.border,
          width: isValid ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.play_circle_fill, color: Colors.redAccent, size: 24),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Paste Hindi YouTube Video URL',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    SizedBox(height: 2),
                    Text(
                      'Supports YouTube videos, Shorts & clips up to 15 min',
                      style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _youtubeUrlController,
            decoration: InputDecoration(
              hintText: 'https://www.youtube.com/watch?v=... or https://youtu.be/...',
              hintStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
              prefixIcon: const Icon(Icons.link, color: AppTheme.primaryLight),
              suffixIcon: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (_youtubeUrlController.text.isNotEmpty)
                    IconButton(
                      icon: const Icon(Icons.clear, size: 20),
                      onPressed: () => setState(() => _youtubeUrlController.clear()),
                    ),
                  TextButton.icon(
                    onPressed: _pasteFromClipboard,
                    icon: const Icon(Icons.content_paste, size: 16),
                    label: const Text('Paste'),
                    style: TextButton.styleFrom(
                      foregroundColor: AppTheme.primaryLight,
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                  const SizedBox(width: 4),
                ],
              ),
              filled: true,
              fillColor: AppTheme.surfaceElevated,
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: const BorderSide(color: AppTheme.border),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: const BorderSide(color: AppTheme.border),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: const BorderSide(color: AppTheme.primaryLight, width: 2),
              ),
            ),
            onChanged: (_) => setState(() {}),
          ),
          if (urlText.isNotEmpty) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(
                  isValid ? Icons.check_circle : Icons.info_outline,
                  size: 16,
                  color: isValid ? Colors.greenAccent : Colors.amberAccent,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    isValid
                        ? 'Valid YouTube video link ready for extraction'
                        : 'Please enter a valid YouTube video or Shorts link',
                    style: TextStyle(
                      fontSize: 12,
                      color: isValid ? Colors.greenAccent : Colors.amberAccent,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSettingsCard() {
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
          const Row(
            children: [
              Icon(Icons.tune, color: AppTheme.primaryLight, size: 20),
              SizedBox(width: 8),
              Text(
                'Dubbing & Voice Settings',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Voice Selection
          const Text('Telugu Neural Voice', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: AppTheme.surfaceElevated,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppTheme.border),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _selectedVoiceId,
                isExpanded: true,
                dropdownColor: AppTheme.surfaceElevated,
                items: _voices.map((v) {
                  return DropdownMenuItem(
                    value: v.voiceId,
                    child: Text('${v.name} (${v.gender})'),
                  );
                }).toList(),
                onChanged: (val) {
                  if (val != null) setState(() => _selectedVoiceId = val);
                },
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Speaking Rate Slider
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Speaking Rate Adjustment', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              Text('${_speakingRate.toStringAsFixed(1)}x', style: const TextStyle(color: AppTheme.primaryLight, fontWeight: FontWeight.bold)),
            ],
          ),
          Slider(
            value: _speakingRate,
            min: 0.8,
            max: 1.3,
            divisions: 5,
            activeColor: AppTheme.primary,
            onChanged: (val) => setState(() => _speakingRate = val),
          ),
          const SizedBox(height: 12),

          // Preserve Background Audio Switch
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Preserve Background Ambience (Music & Effects)', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            subtitle: const Text(
              'Off (Recommended): 100% pure Telugu speech with zero original audio bleed.\nOn: Suppresses original vocals and ducks ambience under Telugu speech.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            value: _preserveBackground,
            activeThumbColor: AppTheme.accent,
            onChanged: (val) => setState(() => _preserveBackground = val),
          ),

          if (_preserveBackground) ...[
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Dialogue Ducking Depth', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                Text('${_duckingDb.toStringAsFixed(0)} dB', style: const TextStyle(color: AppTheme.accent, fontWeight: FontWeight.bold)),
              ],
            ),
            Slider(
              value: _duckingDb,
              min: -24.0,
              max: -6.0,
              divisions: 6,
              activeColor: AppTheme.accent,
              onChanged: (val) => setState(() => _duckingDb = val),
            ),
          ],
        ],
      ),
    );
  }
}
