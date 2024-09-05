from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
import os
import tempfile
from moviepy.editor import AudioFileClip, CompositeVideoClip
import pandas as pd
from PIL import Image

class ProcessVideoView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def logVariable(variable):
        return Response(
                {'message': variable}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def post(self, request, *args, **kwargs):

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

            # Save uploaded files to temporary locations
            temp_audio_file = tempfile.NamedTemporaryFile(delete=False)
            temp_layout_file = tempfile.NamedTemporaryFile(delete=False)
            temp_lyrics_file = tempfile.NamedTemporaryFile(delete=False)

            for chunk in audio_file.chunks():
                temp_audio_file.write(chunk)
            for chunk in layout_file.chunks():
                temp_layout_file.write(chunk)
            for chunk in lyrics_file.chunks():
                temp_lyrics_file.write(chunk)

            logVariable(temp_layout_file.name)

            # Read CSV file for layout
            layout_df = pd.read_csv(temp_layout_file.name)

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

            # Read CSV file for lyrics
            lyrics_df = pd.read_csv(temp_lyrics_file.name)

            # Process audio using MoviePy
            audio_clip = AudioFileClip(temp_audio_file.name)

            # Placeholder for further processing logic (similar to your script)
            # Here you would integrate your video processing logic

            # Example response, modify based on your actual output
            response_data = {
                'status': 'success',
                'message': 'Video processing started. Check back later for the output.',
            }
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
