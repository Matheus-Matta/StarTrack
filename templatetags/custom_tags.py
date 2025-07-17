from django import template

register = template.Library()

@register.filter(name='attr')
def attr(obj, attr_name):
    return getattr(obj, attr_name, "")