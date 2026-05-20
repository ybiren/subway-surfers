import 'dart:async';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import '../main.dart';
import 'prepare_screen.dart';

class GameScreen extends StatefulWidget {
  final AppState appState;
  final CameraController camera;
  const GameScreen({super.key, required this.appState, required this.camera});

  @override
  State<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends State<GameScreen> {
  CameraController get _cam => widget.camera;

  bool _streaming = false;
  bool _capturing = false;
  bool _cameraDisposed = false;
  Timer? _frameTimer;

  int _score = 0;
  int _elapsed = 0; // seconds
  bool _paused = false;
  bool _outOfFrame = false;
  bool _gameOver = false;
  int _coins = 0;

  String _alertText = '';
  Timer? _alertTimer;

  @override
  void initState() {
    super.initState();
    widget.appState.ws.onMessage = _onMessage;
    _startStreaming();
  }

  @override
  void dispose() {
    _frameTimer?.cancel();
    _alertTimer?.cancel();
    if (!_cameraDisposed) _cam.dispose();
    super.dispose();
  }

  void _startStreaming() {
    _streaming = true;
    _frameTimer = Timer.periodic(const Duration(milliseconds: 50), (_) async {
      if (!_streaming || _capturing || !_cam.value.isInitialized) return;
      _capturing = true;
      try {
        final file = await _cam.takePicture();
        final bytes = await file.readAsBytes();
        widget.appState.ws.sendBytes(bytes);
      } catch (_) {} finally {
        _capturing = false;
      }
    });
  }

  void _onMessage(Map<String, dynamic> msg) {
    if (!mounted) return;
    final type = msg['type'] as String?;
    switch (type) {
      case 'pose_feedback':
        final visible = msg['pose_visible'] as bool? ?? false;
        setState(() => _outOfFrame = !visible);
        if (!visible) _showAlert('Step back into frame!');
        break;
      case 'game_state':
        setState(() {
          _score = msg['score'] as int? ?? _score;
          _elapsed = ((msg['time'] as num?)?.toDouble() ?? _elapsed.toDouble()).round();
          _paused = (msg['state'] as String?) == 'paused';
        });
        break;
      case 'game_over':
        setState(() {
          _gameOver = true;
          _score = msg['score'] as int? ?? _score;
          _elapsed = ((msg['time'] as num?)?.toDouble() ?? _elapsed.toDouble()).round();
          _coins = msg['coins'] as int? ?? 0;
          _streaming = false;
        });
        _frameTimer?.cancel();
        break;
    }
  }

  void _showAlert(String text) {
    setState(() => _alertText = text);
    _alertTimer?.cancel();
    _alertTimer = Timer(const Duration(seconds: 3), () {
      if (mounted) setState(() => _alertText = '');
    });
  }

  String _formatTime(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }

  void _onResume() {
    widget.appState.ws.sendJson({'type': 'game_cmd', 'cmd': 'resume'});
  }

  void _onNewGame() async {
    _frameTimer?.cancel();
    _streaming = false;
    _cameraDisposed = true;
    await _cam.dispose();
    if (mounted) {
      Navigator.pushReplacement(context, MaterialPageRoute(
        builder: (_) => PrepareScreen(appState: widget.appState),
      ));
    }
  }

  void _onExit() => Navigator.of(context).popUntil((r) => r.isFirst);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Camera preview
          CameraPreview(_cam),

          // Red border overlay when out of frame
          if (_outOfFrame)
            Positioned.fill(
              child: IgnorePointer(
                child: Container(
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.red.withOpacity(0.6), width: 14),
                  ),
                ),
              ),
            ),

          // Top HUD
          Positioned(
            top: 0, left: 0, right: 0,
            child: Container(
              color: Colors.black.withOpacity(0.55),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: SafeArea(
                bottom: false,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Score: $_score',
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFFFFD700))),
                    Text(_formatTime(_elapsed),
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
                  ],
                ),
              ),
            ),
          ),

          // Alert label
          if (_alertText.isNotEmpty)
            Positioned(
              top: 100, left: 16, right: 16,
              child: Text(
                _alertText,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.redAccent, fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),

          // Pause overlay
          if (_paused && !_gameOver)
            Center(
              child: ElevatedButton(
                onPressed: _onResume,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1A6B33),
                  padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 18),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Resume', style: TextStyle(fontSize: 20)),
              ),
            ),

          // Game over panel
          if (_gameOver)
            Center(
              child: Container(
                width: MediaQuery.of(context).size.width * 0.82,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: const Color(0xEE0F0F26),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('GAME OVER',
                        style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.redAccent)),
                    const SizedBox(height: 16),
                    Text('Score: $_score',
                        style: const TextStyle(fontSize: 20, color: Color(0xFFFFD700))),
                    Text('Time: ${_formatTime(_elapsed)}',
                        style: const TextStyle(fontSize: 18, color: Colors.white)),
                    Text('Coins: $_coins',
                        style: const TextStyle(fontSize: 18, color: Color(0xFFFFD700))),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: _onNewGame,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1E6BE6),
                        minimumSize: const Size(double.infinity, 50),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: const Text('New Game', style: TextStyle(fontSize: 16)),
                    ),
                    const SizedBox(height: 10),
                    ElevatedButton(
                      onPressed: _onExit,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF8B1A1A),
                        minimumSize: const Size(double.infinity, 50),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: const Text('Exit', style: TextStyle(fontSize: 16)),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
