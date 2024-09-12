from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
import os
from moviepy.editor import AudioFileClip, ImageClip, TextClip, CompositeVideoClip, VideoClip
import pandas as pd
from PIL import Image
from io import BytesIO, TextIOWrapper
import traceback
import tempfile
import uuid
import numpy as np
from django.http import FileResponse
#from moviepy.config import change_settings
#change_settings({"IMAGEMAGICK_BINARY": r"C:\\Program Files\\ImageMagick-7.1.1-Q16-HDRI\\magick.exe"})

class ProcessVideoView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):

        # Functions
        def logVariable(variable):
            return Response(
                {'message': variable}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # get the value from column 2 of the row where the first column is equal to key; this how the lyrics.csv file is structured
        def get_value(dataframe, key, col):
            return dataframe[dataframe.iloc[:, 0] == key].iloc[0, col]
        
        def get_color_value(dataframe, key):
            return [dataframe[dataframe.iloc[:, 0] == key].iloc[0, 11],dataframe[dataframe.iloc[:, 0] == key].iloc[0, 12],dataframe[dataframe.iloc[:, 0] == key].iloc[0, 13]]

        # First pass for requried files
        required_files = ['audio.mp3', 'layout.csv', 'lyrics.csv']
        missing_files = [file for file in required_files if file not in request.FILES]

        if missing_files:
            return Response(
                {'error': 'Missing files', 'missing_files': missing_files}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            audio_file = request.FILES['audio.mp3']
            layout_file = request.FILES['layout.csv']
            lyrics_file = request.FILES['lyrics.csv']

            # Read the CSV files received
            layout_df = pd.read_csv(TextIOWrapper(layout_file.file, encoding='utf-8'))
            lyrics_df = pd.read_csv(TextIOWrapper(lyrics_file.file, encoding='utf-8'))

            # Second pass for requried files, based on layout
            for index, row in layout_df.iterrows():
                if row['type'] == 'image':
                    required_files.append(row['img_file'])

            missing_files = [file for file in required_files if file not in request.FILES]

            if missing_files:
                return Response(
                    {'error': 'Missing files', 'missing_files': missing_files}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate a unique filename for the audio to avoid conflicts
            temp_audio_file_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.mp3")

            # Write the uploaded audio file to this path
            with open(temp_audio_file_path, 'wb') as f:
                for chunk in audio_file.chunks():
                    f.write(chunk)

            # Process the audio file using MoviePy
            audio_clip = AudioFileClip(temp_audio_file_path)

            # Code to process data and generate video file

            title = get_value(lyrics_df, 'title', 1)
            voice = get_value(lyrics_df, 'voice', 1)
            writer = get_value(lyrics_df, 'writer', 1)

            # Filter rows where the first column is 'language' and drop columns 2 and 3
            language_row = lyrics_df[lyrics_df.iloc[:, 0] == 'language']
            language_row = language_row.drop(language_row.columns[[0, 1, 2]], axis=1)

            # discard more than 3 languages
            if language_row.shape[1] > 3:
                language_row = language_row.iloc[:, :3]

            # do the same for language directions
            lang_dir_row = lyrics_df[lyrics_df.iloc[:, 0] == 'lang_dir']
            lang_dir_row = lang_dir_row.drop(lang_dir_row.columns[[0, 1, 2]], axis=1)
            
            if lang_dir_row.shape[1] > 3:
                lang_dir_row = lang_dir_row.iloc[:, :3]

            # count again
            language_count = language_row.shape[1]

            # Filter rows where the first column is 'lyrics'
            lyrics_df = lyrics_df[lyrics_df.iloc[:, 0] == 'lyrics']

            # Keep only the first language_count + 2 columns (which represent start and end time)
            lyrics_df = lyrics_df.iloc[:, :(language_count + 3)].drop(lyrics_df.columns[[0]], axis=1)

            # save the number of languages for later
            language_count = lyrics_df.shape[1] - 2     # First two columns are start and end time

            layout_clips = []
            layout_type = get_value(layout_df, 'layout_type', 1)
            
            video_width = int(get_value(layout_df, 'layout_width', 1))
            video_height = int(get_value(layout_df, 'layout_height', 1))

            # layout_rf = video_height / get_value(layout_df, 'layout_type', 7)
            layout_rf = 1 # scale factor for all elements

            def make_frame(t):
                screen_arr = np.zeros((video_height, video_width, 3), dtype=np.int32)  # Array for drawing
                background_color = [17, 51, 0]
                # screen_arr[:, :] = get_color_value(lyrics_df, 'layout_bgcolor', 1)
                screen_arr[:, :] = background_color
                return np.clip(screen_arr, 0, 255).astype('uint8')  # Clip and convert to uint8
            
            bg_clip = VideoClip(make_frame, duration=audio_clip.duration)
            layout_clips.append(bg_clip)

            # Iterate over each row
            for index, row in layout_df.iterrows():
                # Render based on the 'type' column
                if row['type'] == 'image':
                    clip_image = Image.open(request.FILES[row['img_file']])
                    
                    if (clip_image.mode == 'P'):
                        clip_image = clip_image.convert('RGBA')
                        
                    clip_image = clip_image.resize((int(row['width'] * layout_rf), int(row['height'] * layout_rf)))
                    clip_image = np.array(clip_image)
                    clip_image = ImageClip(clip_image).set_position((int(row['x'] * layout_rf), int(row['y'] * layout_rf)))
                    clip_image = clip_image.set_duration(audio_clip.duration)
                    layout_clips.append(clip_image)

                elif row['type'] == 'rectangle':
                    render_rect = True
                    
                    if row['name'] == 'rec_lyrics' and (language_count < 1 ):     
                        render_rect = False
                    elif row['name'] == 'rec_lang1' and (language_count < 2 ):
                        render_rect = False
                    elif row['name'] == 'rec_lang2' and (language_count < 3):
                        render_rect = False

                    if render_rect == True:
                        clip_rect = Image.new("RGBA", (int(row['width'] * layout_rf), int(row['height'] * layout_rf)), (int(row['r']), int(row['g']), int(row['b']), int(row['a'])))
                        clip_rect = ImageClip(np.array(clip_rect), duration=audio_clip.duration, ismask=False).set_position((int(row['x'] * layout_rf), int(row['y'] * layout_rf)))
                        clip_rect = clip_rect.set_duration(audio_clip.duration)
                        layout_clips.append(clip_rect)

                elif row['type'] == 'text':
                    text = row['name']

                    if row['name'] == 'var_title':
                        text = title
                    elif row['name'] == 'var_voice':
                        text = voice
                    elif row['name'] == 'var_writer':
                        text = writer
                    elif row['name'] == 'lbl_lyrics':
                        if lyrics_df.shape[1] >= 1 + 2:   # +2 because of start and end time
                            text = "Lyrics in " + language_row.iloc[0, 0]
                            text = text.upper()
                        else:
                            text = ""
                    elif row['name'] == 'lbl_lang1':
                        if lyrics_df.shape[1] >= 2 + 2:    # +2 because of start and end time
                            text = "Translation in " + language_row.iloc[0, 1]
                            text = text.upper()
                        else:
                            text = ""
                    elif row['name'] == 'lbl_lang2':
                        if lyrics_df.shape[1] >= 3 + 2:    # +2 because of start and end time
                            text = "Translation in " + language_row.iloc[0, 2]
                            text = text.upper()
                        else:
                            text = ""

                    if not text == "":
                        clip_text = TextClip(text, fontsize=row['size'] * layout_rf, color=row['color'], font=row['font'], align='West', size=(int(row['width'] * layout_rf), None), method='caption')
                        clip_text = clip_text.set_position((int(row['x'] * layout_rf), int(row['y'] * layout_rf)))
                        layout_clips.append(clip_text)

                elif row['type'] == 'lyrics':
                    # Replace NaN values with an empty string
                    lyrics_df = lyrics_df.fillna('')

                    lyric_col = -1
                    
                    if row['name'] == 'var_lyrics' and language_count >= 1:
                        lyric_col = 0 + 2
                    elif row['name'] == 'var_lang1' and language_count >= 2:
                        lyric_col = 1 + 2
                    elif row['name'] == 'var_lang2' and language_count >= 3:
                        lyric_col = 2 + 2

                    if lyric_col >= 0:
                        for index, lyric_row in lyrics_df.iterrows():
                            lyric = lyric_row[lyric_col]
                            lang_dir = lang_dir_row.iloc[0, lyric_col - 2]              # -2 because of start and end time
                            
                            text_dir = 'West'
                            if lang_dir == 'rtl':
                                text_dir = 'East'

                            if lyric and not lyric.isspace():
                                clip_lyric = TextClip(lyric, fontsize=row['size'] * layout_rf, color=row['color'], font=row['font'], align=text_dir, size=(int(row['width'] * layout_rf), None), method='caption')
                                clip_lyric = clip_lyric.set_start(lyric_row['start']).set_end(lyric_row['end']).set_position((int(row['x'] * layout_rf), int(row['y'] * layout_rf))).crossfadein(0.5).crossfadeout(0.5)
                                layout_clips.append(clip_lyric)
                    
            # Create a composite clip
            video = CompositeVideoClip(layout_clips, (video_width, video_height)).set_audio(audio_clip)
            video.duration = audio_clip.duration

            temp_video_file_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.mp4")

            # Write the uploaded audio file to this path
            with open(temp_video_file_path, 'wb') as v:
                video.write_videofile(temp_video_file_path, fps=int(get_value(layout_df, 'layout_fps', 1)))

            return FileResponse(open(temp_video_file_path, 'rb'), as_attachment=True, filename="processed_video.mp4")
                 
        except Exception as e:
            error_message = traceback.format_exc()
            return Response({'error': str(e), 'details': error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            audio_clip.close()
            os.remove(temp_audio_file_path)
            # os.remove(temp_video_file_path)  # Clean up video file after serving
