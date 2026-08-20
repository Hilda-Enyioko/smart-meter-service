from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'password2', 'phone_number', 'role')
        extra_kwargs = {'role': {'required': False}}

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': "Password fields didn't match."})
        return attrs

    def validate_role(self, value):
        # Block public registration from self-assigning admin
        if value == User.Role.ADMIN:
            raise serializers.ValidationError("You cannot self-register as an admin.")
        return value

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    """Used for a user viewing/editing their own profile. role is read-only here."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'phone_number', 'role', 'created_at', 'updated_at')
        read_only_fields = ('id', 'role', 'created_at', 'updated_at')


class AdminUserSerializer(serializers.ModelSerializer):
    """Used by admins managing other users — role and is_active are editable."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'phone_number', 'role', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')
