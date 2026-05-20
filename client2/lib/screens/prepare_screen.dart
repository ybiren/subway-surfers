import 'dart:async';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import '../main.dart';
import 'game_screen.dart';

class PrepareScreen extends StatefulWidget {
  final AppState appState;
  const PrepareScreen({super.key, required this.appState});

  @override
  State<PrepareScreen> createState() => _PrepareScreenState();
}

class _PrepareScreenState extends State<PrepareScreen> {
  CameraController? _cam;
  bool _cameraReady = false;
  bool _poseVisible = false;
  bool _streaming = false;
  bool _capturing = false;
  bool _cameraTransferred = false;
  Timer? _frameTimer;
  String _status = 'Position yourself so your full body is visible';
  List<Map<String, dynamic>> _landmarks = [];
  int _framesSent = 0;
  int _feedbackCount = 0;
  String _lastGesture = '-';

  @override
  void initState() {
    super.initState();
    widget.appState.ws.onMessage = _onMessage;
    _initCamera();
  }

  @override
  void dispose() {
    _frameTimer?.cancel();
    if (!_cameraTransferred) _cam?.dispose();
    super.dispose();
  }

  Future<void> _initCamera() async {
    final cameras = await availableCameras();
    if (cameras.isEmpty) return;
    // Prefer front camera
    final cam = cameras.firstWhere(
      (c) => c.lensDirection == CameraLensDirection.front,
      orElse: () => cameras.first,
    );
    _cam = CameraController(cam, ResolutionPreset.low, enableAudio: false);
    await _cam!.initialize();
    if (!mounted) return;
    setState(() => _cameraReady = true);
    _startStreaming();
  }

  void _startStreaming() {
    _streaming = true;
    _frameTimer = Timer.periodic(const Duration(milliseconds: 50), (_) async {
      if (!_streaming || _capturing || _cam == null || !_cam!.value.isInitialized) return;
      _capturing = true;
      try {
        final file = await _cam!.takePicture();
        final bytes = await file.readAsBytes();
        widget.appState.ws.sendBytes(bytes);
        if (mounted) setState(() => _framesSent++);
      } catch (_) {} finally {
        _capturing = false;
      }
    });
  }

  void _onMessage(Map<String, dynamic> msg) {
    if (msg['type'] == 'pose_feedback') {
      final visible = msg['pose_visible'] as bool? ?? false;
      final lm = (msg['landmarks'] as List?)
          ?.map((e) => Map<String, dynamic>.from(e as Map))
          .toList() ?? [];
      if (!mounted) return;
      setState(() {
        _poseVisible = visible;
        _landmarks = lm;
        _feedbackCount++;
        _lastGesture = msg['gesture'] as String? ?? '-';
        _status = visible
            ? 'Ready! Press START when you are set'
            : 'Cannot detect pose — make sure full body is visible';
      });
    }
  }

  void _onStart() {
    widget.appState.ws.sendJson({'type': 'game_cmd', 'cmd': 'start'});
    _frameTimer?.cancel();
    _streaming = false;
    _cameraTransferred = true;
    Navigator.pushReplacement(context, MaterialPageRoute(
      builder: (_) => GameScreen(appState: widget.appState, camera: _cam!),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Camera preview
          if (_cameraReady)
            CameraPreview(_cam!)
          else
            const Center(child: CircularProgressIndicator()),

          // Pose skeleton overlay
          if (_landmarks.isNotEmpty)
            CustomPaint(
              size: Size.infinite,
              painter: _SkeletonPainter(_landmarks),
            ),

          // Top status bar
          Positioned(
            top: 0, left: 0, right: 0,
            child: Container(
              color: Colors.black54,
              padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
              child: SafeArea(
                bottom: false,
                child: Text(
                  _status,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: _poseVisible ? Colors.greenAccent : Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
          ),

          // Debug panel
          Positioned(
            bottom: 120, left: 8,
            child: Container(
              padding: const EdgeInsets.all(8),
              color: Colors.black54,
              child: Text(
                'Frames sent: $_framesSent\n'
                'Server replies: $_feedbackCount\n'
                'Pose: ${_poseVisible ? "✅ DETECTED" : "❌ NOT DETECTED"}\n'
                'Gesture: $_lastGesture',
                style: const TextStyle(color: Colors.white, fontSize: 12, fontFamily: 'monospace'),
              ),
            ),
          ),

          // START button
          Positioned(
            bottom: 40, left: 0, right: 0,
            child: Center(
              child: ElevatedButton(
                onPressed: _poseVisible ? _onStart : null,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _poseVisible
                      ? const Color(0xFF1A9E47)
                      : const Color(0xFF1A9E47).withOpacity(0.35),
                  padding: const EdgeInsets.symmetric(horizontal: 60, vertical: 20),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: const Text('START', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Skeleton connections between landmark indices
const _kConnections = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
];

class _SkeletonPainter extends CustomPainter {
  final List<Map<String, dynamic>> landmarks;
  _SkeletonPainter(this.landmarks);

  @override
  void paint(Canvas canvas, Size size) {
    final dotPaint = Paint()..color = Colors.greenAccent..style = PaintingStyle.fill;
    final linePaint = Paint()..color = Colors.greenAccent.withOpacity(0.7)
        ..strokeWidth = 2.5..style = PaintingStyle.stroke;

    final pts = <int, Offset>{};
    for (final lm in landmarks) {
      final i = lm['i'] as int;
      final x = (lm['x'] as num).toDouble() * size.width;
      final y = (lm['y'] as num).toDouble() * size.height;
      pts[i] = Offset(x, y);
    }

    for (final conn in _kConnections) {
      final a = pts[conn[0]];
      final b = pts[conn[1]];
      if (a != null && b != null) canvas.drawLine(a, b, linePaint);
    }

    for (final p in pts.values) {
      canvas.drawCircle(p, 6, dotPaint);
    }
  }

  @override
  bool shouldRepaint(_SkeletonPainter old) => old.landmarks != landmarks;
}
