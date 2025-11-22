App is not working, tasks are failing when I create new meeting I saw tasks failed and worker-1    | RuntimeError: Conversation transcription canceled: CancellationReason.Error. Timeout while waiting for service to stop SessionId: bef83743f9c14e8c97c46827eb1f7970
worker-1    | backend.application.use_cases.extract_meeting.ExtractionError: Unexpected failure: Conversation transcription canceled: CancellationReason.Error. Timeout while waiting for service to stop SessionId: bef83743f9c14e8c97c46827eb1f7970                                                                                                                   
worker-1    | 2025-11-22 18:05:46,637 ERROR Meeting import job failed for cb771bb9-a44f-499c-895f-f411a1e878a3; message will become visible again                                   


After adding a meeting it's some seconds before the button is enabled again and I can do another meeting, it should be instantly

It's really long to communicate with database and I don't see tasks and meetings for long

It's really long until I see any change, I see queued and nothing is happening. Is this really queued or maybe processing and it's refreshing issue?

Assigned people can be only from /data/voices people. Noone else can be assigned. Diarization should compare voices to /data/voices. Instead I see "Alex" assigned to task. WTF

There are a lot of refreshing issues - I change sth in one view that should be visible in second view but it is not, i have to refresh manually then