/* 题目插图：只渲染通过白名单的内联 SVG。诊断页与孩子端共用，避免两份 sanitizer 漂移。 */
(function () {
  'use strict';
  function el(svg, cls) {
    if (typeof svg !== 'string' || svg.indexOf('<svg') !== 0) return null;
    if (/<\s*script|foreignObject|<\s*image\b|https?:\/\//i.test(svg.replace('xmlns="http://www.w3.org/2000/svg"', ''))) return null;
    var wrap = document.createElement('div');
    wrap.className = cls || 'q-figure';
    wrap.innerHTML = svg;
    var node = wrap.querySelector('svg');
    if (!node) return null;
    node.setAttribute('role', 'img');
    node.setAttribute('aria-hidden', 'true');
    node.setAttribute('focusable', 'false');
    return wrap;
  }
  window.CnmFigure = { el: el };
})();