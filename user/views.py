from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, get_user_model
from .serializers import UserSerializer, RegisterSerializer, LoginSerializer, PasswordChangeSerializer

User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a new user account
    """
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token = Token.objects.get(user=user)
        
        return Response({
            'success': True,
            'message': 'Registration successful',
            'token': token.key,
            'user': UserSerializer(user, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'error': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Login user and return auth token
    """
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': 'Invalid input data'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    
    # Since USERNAME_FIELD is set to 'email' in the User model,
    # we need to authenticate using email, not username
    user = authenticate(username=email, password=password)
    
    if user is None:
        return Response({
            'success': False,
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Get or create token
    token, created = Token.objects.get_or_create(user=user)
    
    return Response({
        'success': True,
        'message': 'Login successful',
        'token': token.key,
        'user': UserSerializer(user, context={'request': request}).data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Logout user by deleting auth token
    """
    try:
        request.user.auth_token.delete()
        return Response({
            'success': True,
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """
    Get current user profile
    """
    user = request.user
    return Response({
        'success': True,
        'user': UserSerializer(user, context={'request': request}).data
    }, status=status.HTTP_200_OK)

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    Update user profile
    """
    user = request.user
    serializer = UserSerializer(user, data=request.data, partial=True, context={'request': request})
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'success': False,
        'error': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password
    """
    serializer = PasswordChangeSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = request.user
    old_password = serializer.validated_data['old_password']
    new_password = serializer.validated_data['new_password']
    
    if not user.check_password(old_password):
        return Response({
            'success': False,
            'error': 'Old password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user.set_password(new_password)
    user.save()
    
    # Update token
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    
    return Response({
        'success': True,
        'message': 'Password changed successfully',
        'token': token.key
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_movie_like(request, movie_id):
    """
    Toggle like status for a movie
    """
    from .models import MovieInteraction
    
    interaction, created = MovieInteraction.objects.get_or_create(
        user=request.user,
        movie_id=movie_id,
        defaults={'is_liked': True}
    )
    
    if not created:
        interaction.is_liked = not interaction.is_liked
        interaction.save()
    
    return Response({
        'success': True,
        'is_liked': interaction.is_liked,
        'message': 'Movie liked' if interaction.is_liked else 'Movie unliked'
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_movie_save(request, movie_id):
    """
    Toggle save status for a movie
    """
    from .models import MovieInteraction
    
    interaction, created = MovieInteraction.objects.get_or_create(
        user=request.user,
        movie_id=movie_id,
        defaults={'is_saved': True}
    )
    
    if not created:
        interaction.is_saved = not interaction.is_saved
        interaction.save()
    
    return Response({
        'success': True,
        'is_saved': interaction.is_saved,
        'message': 'Movie saved' if interaction.is_saved else 'Movie unsaved'
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_movie_interaction(request, movie_id):
    """
    Get user's interaction status for a specific movie
    """
    from .models import MovieInteraction
    
    try:
        interaction = MovieInteraction.objects.get(user=request.user, movie_id=movie_id)
        return Response({
            'success': True,
            'is_liked': interaction.is_liked,
            'is_saved': interaction.is_saved
        }, status=status.HTTP_200_OK)
    except MovieInteraction.DoesNotExist:
        return Response({
            'success': True,
            'is_liked': False,
            'is_saved': False
        }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_saved_movies(request):
    """
    Get all saved movies for the authenticated user
    """
    from .models import MovieInteraction
    
    saved_interactions = MovieInteraction.objects.filter(
        user=request.user,
        is_saved=True
    ).order_by('-updated_at')
    
    saved_movie_ids = [interaction.movie_id for interaction in saved_interactions]
    
    return Response({
        'success': True,
        'movie_ids': saved_movie_ids,
        'count': len(saved_movie_ids)
    }, status=status.HTTP_200_OK)

