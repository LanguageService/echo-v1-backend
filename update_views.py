import re

with open('/Users/sunday/Documents/Project/LetEcho/Echov2/echo-v1-backend/translation/views/structured.py', 'r') as f:
    content = f.read()

# Replace IsAuthenticated with AllowAny
content = content.replace("permission_classes = [permissions.IsAuthenticated]", "permission_classes = [permissions.AllowAny]")

# Update get_queryset
old_get_queryset = """    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)"""

new_get_queryset = """    def get_queryset(self):
        if getattr(self.request.user, 'is_authenticated', False):
            return self.queryset.filter(user=self.request.user)
        return self.queryset.none()"""
content = content.replace(old_get_queryset, new_get_queryset)

with open('/Users/sunday/Documents/Project/LetEcho/Echov2/echo-v1-backend/translation/views/structured.py', 'w') as f:
    f.write(content)
