import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../main.dart';
import 'prepare_screen.dart';

class ConnectScreen extends StatefulWidget {
  final AppState appState;
  const ConnectScreen({super.key, required this.appState});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final _codeCtrl = TextEditingController();
  String _status = '';
  bool _statusError = false;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    widget.appState.ws.onMessage = _onMessage;
  }

  @override
  void dispose() {
    _codeCtrl.dispose();
    super.dispose();
  }

  void _onPair() {
    final code = _codeCtrl.text.trim();
    if (code.length != 6) {
      _setStatus('Enter the full 6-digit code', error: true);
      return;
    }
    setState(() => _loading = true);
    _setStatus('Pairing…');
    widget.appState.ws.sendJson({'type': 'pair', 'code': code});
  }

  void _onMessage(Map<String, dynamic> msg) {
    if (msg['type'] != 'pair_result') return;
    final ok = msg['success'] as bool? ?? false;
    if (ok) {
      if (mounted) {
        Navigator.pushReplacement(context, MaterialPageRoute(
          builder: (_) => PrepareScreen(appState: widget.appState),
        ));
      }
    } else {
      setState(() => _loading = false);
      _setStatus(msg['error'] as String? ?? 'Invalid code — try again', error: true);
    }
  }

  void _setStatus(String text, {bool error = false}) {
    if (!mounted) return;
    setState(() { _status = text; _statusError = error; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text('Pair with PC', style: TextStyle(color: Color(0xFFFFD700))),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 32),
              const Text(
                'Pair with PC',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFFFFD700)),
              ),
              const SizedBox(height: 12),
              const Text(
                'Enter the 6-digit code shown on the game screen',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white54, fontSize: 15),
              ),
              const SizedBox(height: 40),
              TextField(
                controller: _codeCtrl,
                keyboardType: TextInputType.number,
                maxLength: 6,
                textAlign: TextAlign.center,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                style: const TextStyle(fontSize: 32, letterSpacing: 12, color: Color(0xFFFFD700)),
                decoration: InputDecoration(
                  counterText: '',
                  hintText: '_ _ _ _ _ _',
                  hintStyle: const TextStyle(fontSize: 28, color: Colors.white24),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: Color(0xFFFFD700), width: 2),
                  ),
                ),
              ),
              const SizedBox(height: 28),
              ElevatedButton(
                onPressed: _loading ? null : _onPair,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1E6BE6),
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Pair', style: TextStyle(fontSize: 20)),
              ),
              const SizedBox(height: 16),
              if (_loading) const Center(child: CircularProgressIndicator()),
              if (_status.isNotEmpty)
                Text(
                  _status,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: _statusError ? Colors.redAccent : Colors.greenAccent,
                    fontSize: 14,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
