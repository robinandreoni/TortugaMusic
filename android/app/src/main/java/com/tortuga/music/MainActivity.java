package com.tortuga.music;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.support.v4.media.MediaMetadataCompat;
import android.support.v4.media.session.MediaSessionCompat;
import android.support.v4.media.session.PlaybackStateCompat;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.InputStream;
import java.net.URL;

public class MainActivity extends AppCompatActivity {

    private static MainActivity sInstance;
    private static boolean sServerStarted = false;
    private WebView webView;
    private FrameLayout customViewContainer;
    private WebChromeClient.CustomViewCallback customViewCallback;
    private View mCustomView;

    public static void sendMediaCommand(String cmd) {
        if (sInstance != null) {
            sInstance.runOnUiThread(() -> {
                switch (cmd) {
                    case "play":
                        sInstance.evaluateJs("if(window.togglePlay) window.togglePlay(true);");
                        break;
                    case "pause":
                        sInstance.evaluateJs("if(window.togglePlay) window.togglePlay(false);");
                        break;
                    case "toggle":
                        sInstance.evaluateJs("if(window.togglePlay) window.togglePlay();");
                        break;
                    case "next":
                        sInstance.evaluateJs("if(window.nextTrack) window.nextTrack();");
                        break;
                    case "prev":
                        sInstance.evaluateJs("if(window.prevTrack) window.prevTrack();");
                        break;
                }
            });
        }
    }

    public static void sendNativeProgress(double currentSec, double totalSec, boolean isPlaying) {
        if (sInstance != null) {
            sInstance.evaluateJs("if(window.onNativeProgress) window.onNativeProgress(" + currentSec + "," + totalSec + "," + isPlaying + ");");
        }
    }

    public static void sendNativePlaybackState(boolean isPlaying) {
        if (sInstance != null) {
            sInstance.evaluateJs("if(window.onNativePlaybackState) window.onNativePlaybackState(" + isPlaying + ");");
        }
    }

    public static void sendNativeAudioError(String errorMsg) {
        if (sInstance != null) {
            String safe = errorMsg != null ? errorMsg.replace("'", "\\'") : "Errore riproduzione";
            sInstance.evaluateJs("if(window.onNativeAudioError) window.onNativeAudioError('" + safe + "');");
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sInstance = this;

        FrameLayout rootLayout = new FrameLayout(this);
        rootLayout.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        webView = new WebView(this);
        webView.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        rootLayout.addView(webView);

        customViewContainer = new FrameLayout(this);
        customViewContainer.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        customViewContainer.setVisibility(View.GONE);
        customViewContainer.setBackgroundColor(0xFF000000);
        rootLayout.addView(customViewContainer);

        setContentView(rootLayout);

        // Immersive status bar
        getWindow().setStatusBarColor(0xFF0a0a0f);

        // Configure WebView
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.setFocusable(true);
        webView.setFocusableInTouchMode(true);
        webView.requestFocus();

        // Clean User-Agent
        String defaultUserAgent = webView.getSettings().getUserAgentString();
        if (defaultUserAgent != null) {
            String cleanUserAgent = defaultUserAgent.replace("; wv", "").replace("wv)", ")");
            webView.getSettings().setUserAgentString(cleanUserAgent);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                super.onReceivedError(view, errorCode, description, failingUrl);
                if (failingUrl != null && failingUrl.contains("127.0.0.1:5000")) {
                    new Handler(Looper.getMainLooper()).postDelayed(() -> {
                        if (webView != null) webView.loadUrl("http://127.0.0.1:5000/");
                    }, 1000);
                }
            }

            @Override
            public void onReceivedError(WebView view, android.webkit.WebResourceRequest request, android.webkit.WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request != null && request.isForMainFrame() && request.getUrl() != null && request.getUrl().toString().contains("127.0.0.1:5000")) {
                    new Handler(Looper.getMainLooper()).postDelayed(() -> {
                        if (webView != null) webView.loadUrl("http://127.0.0.1:5000/");
                    }, 1000);
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(android.webkit.ConsoleMessage consoleMessage) {
                android.util.Log.d("TortugaMusic", consoleMessage.message() + " -- line " +
                        consoleMessage.lineNumber() + " of " + consoleMessage.sourceId());
                return super.onConsoleMessage(consoleMessage);
            }
        });

        // Request notification permission on Android 13+ (API 33+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 101);
            }
        }

        // JavaScript interface
        webView.addJavascriptInterface(new AndroidBridge(), "AndroidBridge");

        // Initialize Python
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }

        // Run Flask server in background thread once per process
        if (!sServerStarted) {
            sServerStarted = true;
            new Thread(() -> {
                try {
                    Python py = Python.getInstance();
                    PyObject serverModule = py.getModule("server");
                    serverModule.callAttr("run_server");
                } catch (Exception e) {
                    e.printStackTrace();
                    new Handler(Looper.getMainLooper()).post(() -> {
                        Toast.makeText(MainActivity.this, "Errore avvio server: " + e.getMessage(), Toast.LENGTH_LONG).show();
                    });
                }
            }).start();
        }

        // Poll server /api/health before loading URL to prevent ERR_CONNECTION_REFUSED
        new Thread(() -> {
            for (int i = 0; i < 40; i++) {
                try {
                    java.net.HttpURLConnection conn = (java.net.HttpURLConnection) new URL("http://127.0.0.1:5000/api/health").openConnection();
                    conn.setConnectTimeout(600);
                    conn.setReadTimeout(600);
                    if (conn.getResponseCode() == 200) {
                        break;
                    }
                } catch (Exception ignored) {}
                try { Thread.sleep(300); } catch (Exception ignored) {}
            }
            runOnUiThread(() -> {
                if (webView != null) {
                    webView.loadUrl("http://127.0.0.1:5000/");
                }
            });
        }).start();

        enableImmersiveMode();
    }

    private void evaluateJs(String script) {
        runOnUiThread(() -> {
            if (webView != null) {
                webView.evaluateJavascript(script, null);
            }
        });
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (event.getAction() == KeyEvent.ACTION_DOWN) {
            int keyCode = event.getKeyCode();
            switch (keyCode) {
                case KeyEvent.KEYCODE_MEDIA_PLAY:
                    evaluateJs("if(window.togglePlay) window.togglePlay(true);");
                    return true;
                case KeyEvent.KEYCODE_MEDIA_PAUSE:
                    evaluateJs("if(window.togglePlay) window.togglePlay(false);");
                    return true;
                case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
                case KeyEvent.KEYCODE_HEADSETHOOK:
                    evaluateJs("if(window.togglePlay) window.togglePlay();");
                    return true;
                case KeyEvent.KEYCODE_MEDIA_NEXT:
                    evaluateJs("if(window.nextTrack) window.nextTrack();");
                    return true;
                case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                    evaluateJs("if(window.prevTrack) window.prevTrack();");
                    return true;
                case KeyEvent.KEYCODE_MEDIA_STOP:
                    evaluateJs("if(window.togglePlay) window.togglePlay(false);");
                    return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }

    // JavaScript interface
    public class AndroidBridge {

        @JavascriptInterface
        public void playNativeAudio(String url, String title, String artist, String thumb, double durationSec) {
            runOnUiThread(() -> {
                MusicService.playUrl(MainActivity.this, url, title, artist, thumb, (long) durationSec);
            });
        }

        @JavascriptInterface
        public void pauseNativeAudio() {
            runOnUiThread(() -> {
                MusicService.pause(MainActivity.this);
            });
        }

        @JavascriptInterface
        public void resumeNativeAudio() {
            runOnUiThread(() -> {
                MusicService.resume(MainActivity.this);
            });
        }

        @JavascriptInterface
        public void toggleNativeAudio() {
            runOnUiThread(() -> {
                MusicService.toggle(MainActivity.this);
            });
        }

        @JavascriptInterface
        public void seekNativeAudio(double seconds) {
            runOnUiThread(() -> {
                MusicService.seekTo(MainActivity.this, seconds);
            });
        }

        @JavascriptInterface
        public void stopNativeAudio() {
            runOnUiThread(() -> {
                MusicService.stop(MainActivity.this);
            });
        }

        @JavascriptInterface
        public void showToast(String message) {
            runOnUiThread(() -> {
                Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
            });
        }

        @JavascriptInterface
        public void setKeepScreenOn(boolean keepOn) {
            runOnUiThread(() -> {
                if (keepOn) {
                    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                } else {
                    getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                }
            });
        }

        @JavascriptInterface
        public void setOrientation(String orientation) {
            runOnUiThread(() -> {
                try {
                    if ("landscape".equalsIgnoreCase(orientation)) {
                        setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
                    } else if ("portrait".equalsIgnoreCase(orientation)) {
                        setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
                    } else {
                        setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            });
        }

        @JavascriptInterface
        public boolean isTV() {
            return false;
        }

        @JavascriptInterface
        public void openBluetoothSettings() {
            runOnUiThread(() -> {
                try {
                    Intent intent = new Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS);
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(intent);
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Impossibile aprire impostazioni Bluetooth", Toast.LENGTH_SHORT).show();
                }
            });
        }
    }

    private void enableImmersiveMode() {
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        View decorView = getWindow().getDecorView();
        int uiOptions = View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                      | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                      | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                      | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                      | View.SYSTEM_UI_FLAG_FULLSCREEN
                      | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY;
        decorView.setSystemUiVisibility(uiOptions);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            enableImmersiveMode();
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            // Minimize to background instead of killing process
            moveTaskToBack(true);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        enableImmersiveMode();
    }

    @Override
    protected void onPause() {
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        sInstance = null;
        super.onDestroy();
    }
}
