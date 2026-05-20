import 'package:flutter/material.dart';
import '../main.dart';
import 'connect_screen.dart';

class LoginScreen extends StatefulWidget {
  final AppState appState;
  const LoginScreen({super.key, required this.appState});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _ipCtrl = TextEditingController();
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  String _status = '';
  bool _statusError = false;
  bool _loading = false;
  String _pendingAction = 'login';

  @override
  void initState() {
    super.initState();
    final ws = widget.appState.ws;
    ws.onConnected = _onConnected;
    ws.onDisconnected = _onDisconnected;
    ws.onMessage = _onMessage;
  }

  @override
  void dispose() {
    _ipCtrl.dispose();
    _userCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  void _start(String action) {
    final ip = _ipCtrl.text.trim();
    final user = _userCtrl.text.trim();
    final pass = _passCtrl.text;
    if (ip.isEmpty || user.isEmpty || pass.isEmpty) {
      _setStatus('Fill in all fields', error: true);
      return;
    }
    _pendingAction = action;
    widget.appState.serverIp = ip;
    widget.appState.username = user;
    widget.appState.password = pass;
    setState(() { _loading = true; });
    _setStatus('Connecting to server…');
    widget.appState.ws.connect('ws://$ip:8765');
  }

  void _onConnected() {
    if (!mounted) return;
    _setStatus('Connected — authenticating…');
    widget.appState.ws.sendJson({
      'type': 'auth',
      'action': _pendingAction,
      'username': widget.appState.username,
      'password': widget.appState.password,
    });
  }

  void _onDisconnected(String reason) {
    if (!mounted) return;
    setState(() => _loading = false);
    _setStatus('Cannot connect: $reason', error: true);
  }

  void _onMessage(Map<String, dynamic> msg) {
    if (msg['type'] != 'auth_result') return;
    final ok = msg['success'] as bool? ?? false;
    if (ok) {
      widget.appState.username = msg['username'] as String?;
      if (mounted) {
        Navigator.pushReplacement(context, MaterialPageRoute(
          builder: (_) => ConnectScreen(appState: widget.appState),
        ));
      }
    } else {
      setState(() => _loading = false);
      _setStatus(msg['message'] as String? ?? 'Auth failed', error: true);
    }
  }

  void _setStatus(String text, {bool error = false}) {
    if (!mounted) return;
    setState(() { _status = text; _statusError = error; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 32),
              const Text(
                'SUBWAY SURFERS',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 30, fontWeight: FontWeight.bold,
                  color: Color(0xFFFFD700),
                  letterSpacing: 2,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Motion Controller',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 16, color: Colors.white54),
              ),
              const SizedBox(height: 40),
              TextField(
                controller: _ipCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Server IP',
                  hintText: '192.168.1.10',
                  prefixIcon: Icon(Icons.wifi),
                ),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _userCtrl,
                decoration: const InputDecoration(
                  labelText: 'Username',
                  prefixIcon: Icon(Icons.person),
                ),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _passCtrl,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'Password',
                  prefixIcon: Icon(Icons.lock),
                ),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _loading ? null : () => _start('login'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1E6BE6),
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: const Text('Login', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _loading ? null : () => _start('signup'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1A9E47),
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: const Text('Sign Up', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                ],
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
