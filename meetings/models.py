import uuid
from django.db import models


class Meeting(models.Model):
    """Represents an uploaded meeting video and its processing state."""

    class Status(models.TextChoices):
        UPLOADED = 'uploaded', 'Uploaded'
        EXTRACTING = 'extracting', 'Extracting Audio & Frames'
        TRANSCRIBING = 'transcribing', 'Transcribing Audio'
        OCR_PROCESSING = 'ocr_processing', 'Extracting Screen Text'
        SUMMARIZING = 'summarizing', 'Generating Summary'
        EMBEDDING = 'embedding', 'Building Search Index'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    video_file = models.FileField(upload_to='videos/')
    duration_seconds = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    status_detail = models.TextField(blank=True, default='')
    progress = models.IntegerField(default=0)  # 0-100 percentage
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Paths for extracted content
    audio_path = models.CharField(max_length=500, blank=True, default='')
    frames_dir = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class TranscriptSegment(models.Model):
    """A segment of transcribed speech with timestamps."""

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name='transcript_segments'
    )
    start_time = models.FloatField()  # seconds from start
    end_time = models.FloatField()
    text = models.TextField()
    speaker = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"[{self.formatted_start}] {self.text[:60]}"

    @property
    def formatted_start(self):
        mins = int(self.start_time // 60)
        secs = int(self.start_time % 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def formatted_end(self):
        mins = int(self.end_time // 60)
        secs = int(self.end_time % 60)
        return f"{mins:02d}:{secs:02d}"


class ScreenFrame(models.Model):
    """A frame extracted from the meeting video with OCR text."""

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name='screen_frames'
    )
    timestamp = models.FloatField()  # seconds from start of video
    frame_path = models.CharField(max_length=500)  # path to saved frame image
    ocr_text = models.TextField(blank=True, default='')
    is_duplicate = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Frame at {self.formatted_timestamp}"

    @property
    def formatted_timestamp(self):
        mins = int(self.timestamp // 60)
        secs = int(self.timestamp % 60)
        return f"{mins:02d}:{secs:02d}"


class MeetingSummary(models.Model):
    """AI-generated summary with multi-modal correlation."""

    meeting = models.OneToOneField(
        Meeting, on_delete=models.CASCADE, related_name='summary'
    )
    overview = models.TextField(blank=True, default='')
    key_points = models.TextField(blank=True, default='')  # JSON list
    action_items = models.TextField(blank=True, default='')  # JSON list
    correlations = models.TextField(blank=True, default='')  # JSON list of speech↔screen links
    full_summary = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for {self.meeting.title}"
