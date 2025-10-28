# Crachá Template - Badge Printing Template

Este diretório contém os arquivos de template para impressão de crachás do sistema Lar Meimei.

## Arquivos

- `cracha-styles.css` - Estilos CSS para o layout dos crachás
- `cracha-template.html` - Template HTML/Jinja para geração dos crachás
- `cracha-demo.html` - Página de demonstração do layout

## Alterações Implementadas

### Problema Original
O logo estava sempre centralizado, independentemente da presença de foto.

### Solução
Foi implementada uma solução CSS que posiciona o logo de forma condicional:

1. **COM foto**: Logo centralizado (margin-left: -120px)
2. **SEM foto**: Logo no canto superior esquerdo (grid-column: 1/3, margin-left: 5px)

### Mudanças no CSS

```css
/* Base da logo (sem margin-left fixo) */
.logo {
  grid-row: 1/5;
  grid-column: 2/3;
  margin-top: 5px;
  max-width: 210px;
  max-height: 112px;
  width: auto;
  height: auto;
}

/* Quando há foto, centraliza o logo */
.Frente:has(.Foto img) .logo {
  margin-left: -120px;
}

/* Quando não há foto, posiciona no canto superior esquerdo */
.Frente:not(:has(.Foto img)) .logo {
  grid-column: 1/3;
  margin-left: 5px;
}
```

### Mudanças no HTML

Correção da lógica condicional para exibir a foto:
- **Antes**: `{% if stu.imagem == null %}` (mostrava quando null)
- **Depois**: `{% if stu.imagem != null %}` (mostra quando existe)

## Como Testar

Abra o arquivo `cracha-demo.html` em um navegador para visualizar:
1. Exemplo com foto (logo centralizado)
2. Exemplo sem foto (logo no canto superior esquerdo)

## Compatibilidade

A solução utiliza o seletor CSS `:has()` que é suportado em:
- Chrome/Edge 105+
- Firefox 121+
- Safari 15.4+

Para navegadores antigos que não suportam `:has()`, o logo permanecerá na posição padrão (centralizado).
