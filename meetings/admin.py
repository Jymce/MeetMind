from django.contrib import admin
from .models import Meeting, TranscriptSegment, ScreenFrame, MeetingSummary


class TranscriptSegmentInline(admin.TabularInline):
    model = TranscriptSegment
    extra = 0
    readonly_fields = ('start_time', 'end_time', 'text', 'speaker')


class ScreenFrameInline(admin.TabularInline):
    model = ScreenFrame
    extra = 0
    readonly_fields = ('timestamp', 'frame_path', 'ocr_text', 'is_duplicate')


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'progress', 'created_at')
    list_filter = ('status',)
    search_fields = ('title',)
    inlines = [TranscriptSegmentInline, ScreenFrameInline]


@admin.register(MeetingSummary)
class MeetingSummaryAdmin(admin.ModelAdmin):
    list_display = ('meeting', 'created_at')
