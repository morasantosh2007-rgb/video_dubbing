import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dubbing_app/main.dart';
import 'package:dubbing_app/models/job_model.dart';
import 'package:dubbing_app/widgets/step_indicator.dart';

void main() {
  testWidgets('App renders Home Screen with hero title and button', (WidgetTester tester) async {
    await tester.pumpWidget(const HindiToTeluguDubbingApp());
    await tester.pumpAndSettle();

    // Verify app brand and hero texts
    expect(find.text('DubAI'), findsOneWidget);
    expect(find.text('Hindi → Telugu AI Video Dubbing'), findsWidgets);
    expect(find.text('Upload Video to Dub'), findsOneWidget);
  });

  testWidgets('StepIndicator displays correct active and completed states', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: StepIndicator(
            currentStatus: JobStatus.SYNCHRONIZING,
            progress: 75,
          ),
        ),
      ),
    );

    // Verify steps are rendered
    expect(find.text('Video Uploaded'), findsOneWidget);
    expect(find.text('Audio Timings Synchronized'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
  });

  test('SpeechSegment model parses JSON accurately', () {
    final json = {
      'segment_id': 1,
      'start': 2.1,
      'end': 4.8,
      'duration': 2.7,
      'hindi_text': 'आप कैसे हैं?',
      'telugu_text': 'మీరు ఎలా ఉన్నారు?',
      'speaker': 'Speaker 1',
      'speed_ratio': 1.05
    };

    final segment = SpeechSegment.fromJson(json);
    expect(segment.segmentId, 1);
    expect(segment.start, 2.1);
    expect(segment.end, 4.8);
    expect(segment.hindiText, 'आप कैसे हैं?');
    expect(segment.teluguText, 'మీరు ఎలా ఉన్నారు?');
    expect(segment.formattedStart, '00:02.10');
    expect(segment.speedRatio, 1.05);
  });
}
