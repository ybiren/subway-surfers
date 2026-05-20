import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:web_socket_channel/web_socket_channel.dart';

typedef MsgCallback = void Function(Map<String, dynamic> msg);
typedef VoidCallback2 = void Function();
typedef StringCallback = void Function(String reason);

class WSClient {
  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  bool _running = false;
  String? _uri;

  MsgCallback? onMessage;
  VoidCallback2? onConnected;
  StringCallback? onDisconnected;

  bool get isConnected => _channel != null;

  void connect(String uri) {
    _uri = uri;
    _running = true;
    _doConnect();
  }

  Future<void> _doConnect() async {
    try {
      _channel = WebSocketChannel.connect(Uri.parse(_uri!));
      onConnected?.call();
      _sub = _channel!.stream.listen(
        (data) {
          if (data is String) {
            try {
              final msg = json.decode(data) as Map<String, dynamic>;
              onMessage?.call(msg);
            } catch (_) {}
          }
        },
        onError: (e) => _handleDisconnect(e.toString()),
        onDone: () => _handleDisconnect('Connection closed'),
      );
    } catch (e) {
      _handleDisconnect(e.toString());
    }
  }

  void _handleDisconnect(String reason) {
    _channel = null;
    onDisconnected?.call(reason);
    if (_running) {
      Future.delayed(const Duration(seconds: 2), _doConnect);
    }
  }

  void disconnect() {
    _running = false;
    _sub?.cancel();
    _channel?.sink.close();
    _channel = null;
  }

  void sendJson(Map<String, dynamic> data) {
    try {
      _channel?.sink.add(json.encode(data));
    } catch (_) {}
  }

  void sendBytes(Uint8List data) {
    try {
      _channel?.sink.add(data);
    } catch (_) {}
  }
}
