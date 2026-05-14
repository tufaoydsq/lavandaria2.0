from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
import json
from core.models import ItemServico


def ver_artigo(request):
    """
    View para página de gerenciamento de artigos
    """
    return render(request, "artigos/artigos.html")


@csrf_exempt
@require_http_methods(["GET"])
def listar_artigos(request):
    """
    API: Listar todos os artigos
    """
    artigos = ItemServico.objects.all().order_by('-id')

    artigos_data = []
    for artigo in artigos:
        artigos_data.append({
            'id': artigo.id,
            'nome': artigo.nome,
            'preco_base': float(artigo.preco_base),
            'preco_formatado': artigo.get_preco_formatado(),
            'disponivel': artigo.disponivel,
            'criado_em': artigo.criado_em.strftime('%Y-%m-%d %H:%M') if hasattr(artigo,
                                                                                'criado_em') else timezone.now().strftime(
                '%Y-%m-%d')
        })

    return JsonResponse({'success': True, 'artigos': artigos_data})


@csrf_exempt
@require_http_methods(["POST"])
def criar_artigo(request):
    """
    API: Criar novo artigo
    """
    try:
        data = json.loads(request.body)
        nome = data.get('nome')
        preco_base = Decimal(str(data.get('preco_base')))
        disponivel = data.get('disponivel', True)

        if not nome:
            return JsonResponse({'success': False, 'error': 'Nome é obrigatório'}, status=400)

        if preco_base < 0:
            return JsonResponse({'success': False, 'error': 'Preço não pode ser negativo'}, status=400)

        artigo = ItemServico.objects.create(
            nome=nome,
            preco_base=preco_base,
            disponivel=disponivel
        )

        return JsonResponse({
            'success': True,
            'artigo': {
                'id': artigo.id,
                'nome': artigo.nome,
                'preco_base': float(artigo.preco_base),
                'preco_formatado': artigo.get_preco_formatado(),
                'disponivel': artigo.disponivel
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
def editar_artigo(request, id):
    """
    API: Editar artigo existente
    """
    try:
        artigo = get_object_or_404(ItemServico, id=id)
        data = json.loads(request.body)

        if 'nome' in data:
            artigo.nome = data['nome']
        if 'preco_base' in data:
            preco_base = Decimal(str(data['preco_base']))
            if preco_base < 0:
                return JsonResponse({'success': False, 'error': 'Preço não pode ser negativo'}, status=400)
            artigo.preco_base = preco_base
        if 'disponivel' in data:
            artigo.disponivel = data['disponivel']

        artigo.save()

        return JsonResponse({
            'success': True,
            'artigo': {
                'id': artigo.id,
                'nome': artigo.nome,
                'preco_base': float(artigo.preco_base),
                'preco_formatado': artigo.get_preco_formatado(),
                'disponivel': artigo.disponivel
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PATCH"])
def alternar_status_artigo(request, id):
    """
    API: Alternar status (disponível/indisponível) do artigo
    """
    try:
        artigo = get_object_or_404(ItemServico, id=id)
        artigo.disponivel = not artigo.disponivel
        artigo.save()

        return JsonResponse({
            'success': True,
            'disponivel': artigo.disponivel,
            'message': f'Artigo {artigo.nome} {"ativado" if artigo.disponivel else "desativado"} com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
def excluir_artigo(request, id):
    """
    API: Excluir artigo
    """
    try:
        artigo = get_object_or_404(ItemServico, id=id)
        nome = artigo.nome
        artigo.delete()

        return JsonResponse({
            'success': True,
            'message': f'Artigo "{nome}" excluído com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
def excluir_multiplos_artigos(request):
    """
    API: Excluir múltiplos artigos
    """
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        if not ids:
            return JsonResponse({'success': False, 'error': 'Nenhum artigo selecionado'}, status=400)

        artigos = ItemServico.objects.filter(id__in=ids)
        quantidade = artigos.count()
        artigos.delete()

        return JsonResponse({
            'success': True,
            'message': f'{quantidade} artigo(s) excluído(s) com sucesso'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)