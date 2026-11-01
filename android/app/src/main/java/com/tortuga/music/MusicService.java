package com.tortuga.music;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.support.v4.media.MediaMetadataCompat;
import android.support.v4.media.session.MediaSessionCompat;
import android.support.v4.media.session.PlaybackStateCompat;
import androidx.core.app.NotificationCompat;
import android.view.KeyEvent;

import java.io.InputStream;
import java.net.URL;

public class MusicService extends Service implements
        MediaPlayer.OnPreparedListener,
        MediaPlayer.OnCompletionListener,
        MediaPlayer.OnErrorListener,
        AudioManager.OnAudioFocusChangeListener {

    public static final String ACTION_PLAY_URL = "com.tortuga.music.ACTION_PLAY_URL";
    public static final String ACTION_PLAY = "com.tortuga.music.ACTION_PLAY";
    public static final String ACTION_PAUSE = "com.tortuga.music.ACTION_PAUSE";
    public static final String ACTION_TOGGLE = "com.tortuga.music.ACTION_TOGGLE";
    public static final String ACTION_NEXT = "com.tortuga.music.ACTION_NEXT";
    public static final String ACTION_PREV = "com.tortuga.music.ACTION_PREV";
    public static final String ACTION_STOP = "com.tortuga.music.ACTION_STOP";
    public static final String ACTION_SEEK = "com.tortuga.music.ACTION_SEEK";

    public static final String EXTRA_URL = "extra_url";
    public static final String EXTRA_TITLE = "extra_title";
    public static final String EXTRA_ARTIST = "extra_artist";
    public static final String EXTRA_THUMB = "extra_thumb";
    public static final String EXTRA_DURATION = "extra_duration";
    public static final String EXTRA_SEEK_POS = "extra_seek_pos";

    private static final String CHANNEL_ID = "tortuga_playback_channel";
    private static final int NOTIFICATION_ID = 1001;

    private static MusicService sInstance = null;
    private static MediaSessionCompat sMediaSession = null;

    private MediaSessionCompat mediaSession;
    private MediaPlayer mediaPlayer;
    private AudioManager audioManager;
    private PowerManager.WakeLock wakeLock;
    private WifiManager.WifiLock wifiLock;
    private NotificationManager notificationManager;
    private Handler progressHandler;
    private Runnable progressRunnable;

    private String currentUrl = "";
    private String currentTitle = "Tortuga Music";
    private String currentArtist = "In riproduzione";
    private String currentThumbUrl = "";
    private Bitmap currentArtBitmap = null;
    private long currentDurationMs = 0;
    private boolean isPlaying = false;
    private boolean isPreparing = false;

    public static MusicService getInstance() {
        return sInstance;
    }

    public static void setMediaSession(MediaSessionCompat session) {
        if (session != null) {
            sMediaSession = session;
        }
    }

    public static void playUrl(Context context, String url, String title, String artist, String thumb, long durationSec) {
        Intent intent = new Intent(context, MusicService.class);
        intent.setAction(ACTION_PLAY_URL);
        intent.putExtra(EXTRA_URL, url);
        intent.putExtra(EXTRA_TITLE, title);
        intent.putExtra(EXTRA_ARTIST, artist);
        intent.putExtra(EXTRA_THUMB, thumb);
        intent.putExtra(EXTRA_DURATION, durationSec * 1000);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent);
            } else {
                context.startService(intent);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void pause(Context context) {
        if (sInstance != null) {
            sInstance.handlePause();
            return;
        }
        Intent intent = new Intent(context, MusicService.class);
        intent.setAction(ACTION_PAUSE);
        try { context.startService(intent); } catch (Exception ignored) {}
    }

    public static void resume(Context context) {
        if (sInstance != null) {
            sInstance.handleResume();
            return;
        }
        Intent intent = new Intent(context, MusicService.class);
        intent.setAction(ACTION_PLAY);
        try { context.startService(intent); } catch (Exception ignored) {}
    }

    public static void toggle(Context context) {
        if (sInstance != null) {
            if (sInstance.isPlaying) sInstance.handlePause(); else sInstance.handleResume();
            return;
        }
        Intent intent = new Intent(context, MusicService.class);
        intent.setAction(ACTION_TOGGLE);
        try { context.startService(intent); } catch (Exception ignored) {}
    }

    public static void seekTo(Context context, double seconds) {
        if (sInstance != null) {
            sInstance.handleSeek((long)(seconds * 1000));
            return;
        }
        Intent intent = new Intent(context, MusicService.class);
        intent.setAction(ACTION_SEEK);
        intent.putExtra(EXTRA_SEEK_POS, (long)(seconds * 1000));
        try { context.startService(intent); } catch (Exception ignored) {}
    }

    public static void stop(Context context) {
        if (sInstance != null) {
            sInstance.handleStop();
            return;
        }
        Intent intent = new Intent(context, MusicService.class);
        intent.setAction(ACTION_STOP);
        try { context.startService(intent); } catch (Exception ignored) {}
    }

    @Override
    public void onCreate() {
        super.onCreate();
        sInstance = this;
        audioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
        notificationManager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        progressHandler = new Handler(Looper.getMainLooper());
        createNotificationChannel();
        initMediaPlayer();
        initMediaSession();
        setupProgressTicker();
    }

    private void initMediaSession() {
        try {
            if (mediaSession != null) {
                try { mediaSession.release(); } catch (Exception ignored) {}
            }
            mediaSession = new MediaSessionCompat(this, "TortugaMusicSession");
            mediaSession.setFlags(MediaSessionCompat.FLAG_HANDLES_MEDIA_BUTTONS |
                                  MediaSessionCompat.FLAG_HANDLES_TRANSPORT_CONTROLS);

            PlaybackStateCompat.Builder stateBuilder = new PlaybackStateCompat.Builder()
                    .setActions(PlaybackStateCompat.ACTION_PLAY |
                                PlaybackStateCompat.ACTION_PAUSE |
                                PlaybackStateCompat.ACTION_PLAY_PAUSE |
                                PlaybackStateCompat.ACTION_SKIP_TO_NEXT |
                                PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS |
                                PlaybackStateCompat.ACTION_STOP |
                                PlaybackStateCompat.ACTION_SEEK_TO)
                    .setState(PlaybackStateCompat.STATE_NONE, 0, 1.0f);
            mediaSession.setPlaybackState(stateBuilder.build());

            mediaSession.setCallback(new MediaSessionCompat.Callback() {
                @Override
                public void onPlay() {
                    handleResume();
                }

                @Override
                public void onPause() {
                    handlePause();
                }

                @Override
                public void onSkipToNext() {
                    MainActivity.sendMediaCommand("next");
                }

                @Override
                public void onSkipToPrevious() {
                    MainActivity.sendMediaCommand("prev");
                }

                @Override
                public void onStop() {
                    handleStop();
                }

                @Override
                public void onSeekTo(long pos) {
                    handleSeek(pos);
                }

                @Override
                public boolean onMediaButtonEvent(Intent mediaButtonEvent) {
                    KeyEvent keyEvent = mediaButtonEvent.getParcelableExtra(Intent.EXTRA_KEY_EVENT);
                    if (keyEvent != null && keyEvent.getAction() == KeyEvent.ACTION_DOWN) {
                        switch (keyEvent.getKeyCode()) {
                            case KeyEvent.KEYCODE_MEDIA_NEXT:
                                onSkipToNext();
                                return true;
                            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                                onSkipToPrevious();
                                return true;
                            case KeyEvent.KEYCODE_MEDIA_PLAY:
                                onPlay();
                                return true;
                            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                                onPause();
                                return true;
                            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
                            case KeyEvent.KEYCODE_HEADSETHOOK:
                                if (isPlaying) handlePause(); else handleResume();
                                return true;
                        }
                    }
                    return super.onMediaButtonEvent(mediaButtonEvent);
                }
            });

            mediaSession.setActive(true);
            sMediaSession = mediaSession;
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void initMediaPlayer() {
        if (mediaPlayer != null) {
            try {
                mediaPlayer.reset();
                mediaPlayer.release();
            } catch (Exception ignored) {}
        }
        mediaPlayer = new MediaPlayer();
        mediaPlayer.setAudioAttributes(new AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .build());
        mediaPlayer.setWakeMode(getApplicationContext(), PowerManager.PARTIAL_WAKE_LOCK);
        mediaPlayer.setOnPreparedListener(this);
        mediaPlayer.setOnCompletionListener(this);
        mediaPlayer.setOnErrorListener(this);
    }

    private void setupProgressTicker() {
        progressRunnable = new Runnable() {
            @Override
            public void run() {
                if (mediaPlayer != null && isPlaying) {
                    try {
                        int posMs = mediaPlayer.getCurrentPosition();
                        int durMs = mediaPlayer.getDuration();
                        if (durMs <= 0 && currentDurationMs > 0) {
                            durMs = (int) currentDurationMs;
                        }
                        MainActivity.sendNativeProgress(posMs / 1000.0, durMs / 1000.0, true);
                    } catch (Exception ignored) {}
                }
                if (isPlaying) {
                    progressHandler.postDelayed(this, 350);
                }
            }
        };
    }

    private void acquireLocks() {
        try {
            if (wakeLock == null) {
                PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
                wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "TortugaMusic:NativeWakeLock");
                wakeLock.setReferenceCounted(false);
            }
            if (!wakeLock.isHeld()) {
                wakeLock.acquire(8 * 60 * 60 * 1000L); // 8 ore
            }

            if (wifiLock == null) {
                WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
                wifiLock = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "TortugaMusic:NativeWifiLock");
                wifiLock.setReferenceCounted(false);
            }
            if (!wifiLock.isHeld()) {
                wifiLock.acquire();
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void releaseLocks() {
        try {
            if (wakeLock != null && wakeLock.isHeld()) {
                wakeLock.release();
            }
            if (wifiLock != null && wifiLock.isHeld()) {
                wifiLock.release();
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Riproduzione Audio Tortuga",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Controlli audio in background e schermata di blocco");
            channel.setShowBadge(false);
            channel.setSound(null, null);
            if (notificationManager != null) {
                notificationManager.createNotificationChannel(channel);
            }
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && intent.getAction() != null) {
            String action = intent.getAction();
            switch (action) {
                case ACTION_PLAY_URL:
                    String url = intent.getStringExtra(EXTRA_URL);
                    String title = intent.getStringExtra(EXTRA_TITLE);
                    String artist = intent.getStringExtra(EXTRA_ARTIST);
                    String thumb = intent.getStringExtra(EXTRA_THUMB);
                    long durationMs = intent.getLongExtra(EXTRA_DURATION, 0);
                    handlePlayUrl(url, title, artist, thumb, durationMs);
                    break;
                case ACTION_PLAY:
                    handleResume();
                    break;
                case ACTION_PAUSE:
                    handlePause();
                    break;
                case ACTION_TOGGLE:
                    if (isPlaying) handlePause(); else handleResume();
                    break;
                case ACTION_NEXT:
                    MainActivity.sendMediaCommand("next");
                    break;
                case ACTION_PREV:
                    MainActivity.sendMediaCommand("prev");
                    break;
                case ACTION_SEEK:
                    long seekPos = intent.getLongExtra(EXTRA_SEEK_POS, 0);
                    handleSeek(seekPos);
                    break;
                case ACTION_STOP:
                    handleStop();
                    break;
            }
        }
        return START_STICKY;
    }

    private void handlePlayUrl(String url, String title, String artist, String thumb, long durationMs) {
        if (url == null || url.isEmpty()) return;
        currentUrl = url;
        currentTitle = title != null ? title : "Tortuga Music";
        currentArtist = artist != null ? artist : "Artista";
        currentThumbUrl = thumb != null ? thumb : "";
        currentDurationMs = durationMs;
        currentArtBitmap = null;

        acquireLocks();
        updateNotification();
        fetchArtworkAsync(currentThumbUrl);

        try {
            if (audioManager != null) {
                audioManager.requestAudioFocus(this, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN);
            }
            if (mediaPlayer == null) {
                initMediaPlayer();
            }
            mediaPlayer.reset();
            isPreparing = true;

            String resolvedUrl = url;
            if (resolvedUrl.startsWith("/")) {
                resolvedUrl = "http://127.0.0.1:5000" + resolvedUrl;
            }

            if (resolvedUrl.startsWith("http://") || resolvedUrl.startsWith("https://")) {
                java.util.Map<String, String> headers = new java.util.HashMap<>();
                headers.put("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36");
                headers.put("Accept", "*/*");
                headers.put("Accept-Encoding", "identity");
                mediaPlayer.setDataSource(this, Uri.parse(resolvedUrl), headers);
            } else {
                mediaPlayer.setDataSource(this, Uri.parse(resolvedUrl));
            }
            mediaPlayer.prepareAsync();
        } catch (Exception e) {
            e.printStackTrace();
            isPreparing = false;
            MainActivity.sendNativeAudioError(e.getMessage());
        }
    }

    @Override
    public void onPrepared(MediaPlayer mp) {
        isPreparing = false;
        try {
            mp.start();
            isPlaying = true;
            acquireLocks();
            updateNotification();
            updateMediaSessionState();
            MainActivity.sendNativePlaybackState(true);
            progressHandler.removeCallbacks(progressRunnable);
            progressHandler.post(progressRunnable);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void handleResume() {
        if (mediaPlayer != null && !isPlaying && !isPreparing) {
            try {
                if (audioManager != null) {
                    audioManager.requestAudioFocus(this, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN);
                }
                mediaPlayer.start();
                isPlaying = true;
                acquireLocks();
                updateNotification();
                updateMediaSessionState();
                MainActivity.sendNativePlaybackState(true);
                progressHandler.removeCallbacks(progressRunnable);
                progressHandler.post(progressRunnable);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    private void handlePause() {
        if (mediaPlayer != null && isPlaying) {
            try {
                mediaPlayer.pause();
                isPlaying = false;
                updateNotification();
                updateMediaSessionState();
                MainActivity.sendNativePlaybackState(false);
                progressHandler.removeCallbacks(progressRunnable);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    private void handleSeek(long posMs) {
        if (mediaPlayer != null) {
            try {
                mediaPlayer.seekTo((int) posMs);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    private void handleStop() {
        isPlaying = false;
        progressHandler.removeCallbacks(progressRunnable);
        if (mediaPlayer != null) {
            try {
                mediaPlayer.stop();
                mediaPlayer.reset();
            } catch (Exception ignored) {}
        }
        releaseLocks();
        stopForeground(true);
        stopSelf();
    }

    @Override
    public void onCompletion(MediaPlayer mp) {
        isPlaying = false;
        progressHandler.removeCallbacks(progressRunnable);
        MainActivity.sendMediaCommand("next");
    }

    @Override
    public boolean onError(MediaPlayer mp, int what, int extra) {
        isPreparing = false;
        isPlaying = false;
        progressHandler.removeCallbacks(progressRunnable);
        initMediaPlayer();
        MainActivity.sendNativeAudioError("Media Error " + what + ":" + extra);
        return true;
    }

    @Override
    public void onAudioFocusChange(int focusChange) {
        if (focusChange == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT ||
            focusChange == AudioManager.AUDIOFOCUS_LOSS) {
            handlePause();
        } else if (focusChange == AudioManager.AUDIOFOCUS_GAIN) {
            handleResume();
        }
    }

    private void fetchArtworkAsync(String thumbUrl) {
        if (thumbUrl != null && !thumbUrl.isEmpty() && thumbUrl.startsWith("http")) {
            new Thread(() -> {
                try {
                    URL u = new URL(thumbUrl);
                    InputStream is = u.openStream();
                    Bitmap b = BitmapFactory.decodeStream(is);
                    if (b != null) {
                        // Downscale if image exceeds 512px to prevent TransactionTooLargeException
                        int maxDim = 512;
                        if (b.getWidth() > maxDim || b.getHeight() > maxDim) {
                            float ratio = Math.min((float) maxDim / b.getWidth(), (float) maxDim / b.getHeight());
                            int targetW = Math.max(1, Math.round(b.getWidth() * ratio));
                            int targetH = Math.max(1, Math.round(b.getHeight() * ratio));
                            Bitmap scaled = Bitmap.createScaledBitmap(b, targetW, targetH, true);
                            if (scaled != b) {
                                b.recycle();
                                b = scaled;
                            }
                        }
                        currentArtBitmap = b;
                        new Handler(Looper.getMainLooper()).post(() -> {
                            updateNotification();
                            updateMediaSessionState();
                        });
                    }
                } catch (Exception ignored) {}
            }).start();
        }
    }

    private void updateMediaSessionState() {
        if (sMediaSession != null) {
            try {
                int state = isPlaying ? PlaybackStateCompat.STATE_PLAYING : PlaybackStateCompat.STATE_PAUSED;
                long pos = mediaPlayer != null ? mediaPlayer.getCurrentPosition() : 0;
                PlaybackStateCompat.Builder stateBuilder = new PlaybackStateCompat.Builder()
                        .setActions(PlaybackStateCompat.ACTION_PLAY |
                                    PlaybackStateCompat.ACTION_PAUSE |
                                    PlaybackStateCompat.ACTION_PLAY_PAUSE |
                                    PlaybackStateCompat.ACTION_SKIP_TO_NEXT |
                                    PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS |
                                    PlaybackStateCompat.ACTION_STOP |
                                    PlaybackStateCompat.ACTION_SEEK_TO)
                        .setState(state, pos, 1.0f);
                sMediaSession.setPlaybackState(stateBuilder.build());

                MediaMetadataCompat.Builder metaBuilder = new MediaMetadataCompat.Builder()
                        .putString(MediaMetadataCompat.METADATA_KEY_TITLE, currentTitle)
                        .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, currentArtist)
                        .putString(MediaMetadataCompat.METADATA_KEY_ALBUM, "Tortuga Music")
                        .putLong(MediaMetadataCompat.METADATA_KEY_DURATION, currentDurationMs);

                if (currentArtBitmap != null) {
                    metaBuilder.putBitmap(MediaMetadataCompat.METADATA_KEY_ALBUM_ART, currentArtBitmap);
                    metaBuilder.putBitmap(MediaMetadataCompat.METADATA_KEY_ART, currentArtBitmap);
                }
                sMediaSession.setMetadata(metaBuilder.build());
                sMediaSession.setActive(true);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    private void updateNotification() {
        try {
            Notification notification = buildNotification();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
            } else {
                startForeground(NOTIFICATION_ID, notification);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private Notification buildNotification() {
        Intent activityIntent = new Intent(this, MainActivity.class);
        activityIntent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this, 0, activityIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        PendingIntent prevIntent = PendingIntent.getService(
                this, 1, new Intent(this, MusicService.class).setAction(ACTION_PREV),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        PendingIntent toggleIntent = PendingIntent.getService(
                this, 2, new Intent(this, MusicService.class).setAction(ACTION_TOGGLE),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        PendingIntent nextIntent = PendingIntent.getService(
                this, 3, new Intent(this, MusicService.class).setAction(ACTION_NEXT),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        int playPauseIcon = isPlaying ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play;
        String playPauseTitle = isPlaying ? "Pausa" : "Play";

        androidx.media.app.NotificationCompat.MediaStyle mediaStyle = new androidx.media.app.NotificationCompat.MediaStyle()
                .setShowActionsInCompactView(0, 1, 2);

        if (sMediaSession != null) {
            mediaStyle.setMediaSession(sMediaSession.getSessionToken());
        }

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle(currentTitle)
                .setContentText(currentArtist)
                .setContentIntent(contentIntent)
                .setOngoing(isPlaying)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setStyle(mediaStyle)
                .addAction(android.R.drawable.ic_media_previous, "Precedente", prevIntent)
                .addAction(playPauseIcon, playPauseTitle, toggleIntent)
                .addAction(android.R.drawable.ic_media_next, "Successivo", nextIntent);

        if (currentArtBitmap != null) {
            builder.setLargeIcon(currentArtBitmap);
        }

        return builder.build();
    }

    @Override
    public void onDestroy() {
        sInstance = null;
        if (mediaPlayer != null) {
            try {
                mediaPlayer.reset();
                mediaPlayer.release();
                mediaPlayer = null;
            } catch (Exception ignored) {}
        }
        if (mediaSession != null) {
            try {
                mediaSession.setActive(false);
                mediaSession.release();
                mediaSession = null;
            } catch (Exception ignored) {}
            sMediaSession = null;
        }
        releaseLocks();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
