from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, get_user_model
from .serializers import UserSerializer, RegisterSerializer, LoginSerializer, PasswordChangeSerializer
from .throttles import LoginRateThrottle, RegisterRateThrottle, PasswordChangeThrottle, ProfileUpdateThrottle
from .authentication import set_auth_cookie, clear_auth_cookie

User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterRateThrottle])
def register(request):
    """
    Register a new user account
    """
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token = Token.objects.get(user=user)
        
        response = Response({
            'success': True,
            'message': 'Registration successful',
            'user': UserSerializer(user, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)
        
        # Set HTTP-only cookie with auth token (XSS safe)
        set_auth_cookie(response, token.key)
        return response
    
    return Response({
        'success': False,
        'error': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login(request):
    """
    Login user and return auth token.
    Rate limited to prevent brute force attacks.
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
    
    response = Response({
        'success': True,
        'message': 'Login successful',
        'user': UserSerializer(user, context={'request': request}).data
    }, status=status.HTTP_200_OK)
    
    # Set HTTP-only cookie with auth token (XSS safe)
    set_auth_cookie(response, token.key)
    return response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Logout user by deleting auth token and clearing cookie
    """
    try:
        request.user.auth_token.delete()
        response = Response({
            'success': True,
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
        
        # Clear the HTTP-only auth cookie
        clear_auth_cookie(response)
        return response
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
@throttle_classes([ProfileUpdateThrottle])
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

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@throttle_classes([ProfileUpdateThrottle])
def update_avatar(request):
    """
    Update user avatar/profile picture
    """
    user = request.user
    
    if 'avatar' not in request.FILES:
        return Response({
            'success': False,
            'error': 'No avatar file provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    avatar_file = request.FILES['avatar']
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if avatar_file.content_type not in allowed_types:
        return Response({
            'success': False,
            'error': 'Invalid file type. Allowed: JPEG, PNG, GIF, WebP'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate file size (max 5MB)
    if avatar_file.size > 5 * 1024 * 1024:
        return Response({
            'success': False,
            'error': 'File too large. Maximum size is 5MB'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Delete old avatar if exists
    if user.avatar:
        user.avatar.delete(save=False)
    
    user.avatar = avatar_file
    user.save()
    
    return Response({
        'success': True,
        'message': 'Avatar updated successfully',
        'avatar_url': request.build_absolute_uri(user.avatar.url) if user.avatar else None,
        'user': UserSerializer(user, context={'request': request}).data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([PasswordChangeThrottle])
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
def rate_movie(request, movie_id):
    """
    Set or update user's rating for a movie (0-5 with 0.5 increments)
    """
    from .models import MovieInteraction
    from decimal import Decimal
    
    rating_value = request.data.get('rating')
    
    if rating_value is None:
        return Response({
            'success': False,
            'error': 'Rating value is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        rating_value = Decimal(str(rating_value))
        if rating_value < 0 or rating_value > 5:
            raise ValueError("Rating must be between 0 and 5")
        # Ensure it's a multiple of 0.5
        if float(rating_value) % 0.5 != 0:
            raise ValueError("Rating must be in 0.5 increments")
    except (ValueError, Exception) as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    interaction, created = MovieInteraction.objects.get_or_create(
        user=request.user,
        movie_id=movie_id,
        defaults={'rating': rating_value}
    )
    
    if not created:
        interaction.rating = rating_value
        interaction.save()
    
    return Response({
        'success': True,
        'rating': float(interaction.rating) if interaction.rating else None,
        'message': 'Movie rated successfully'
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
            'rating': float(interaction.rating) if interaction.rating else None,
            'is_saved': interaction.is_saved
        }, status=status.HTTP_200_OK)
    except MovieInteraction.DoesNotExist:
        return Response({
            'success': True,
            'rating': None,
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

