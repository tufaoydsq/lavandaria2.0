from django.shortcuts import render

# Create your views here.
def ver_funcionarios(request):

    return render(request, 'funcionarios/funcionarios.html')