// Sidebar accordion fix for Visualizations & Descriptive Statistics
// Purpose: provide toggleAccordion(accId) and ensure submenu elements are shown/hidden.

(function () {
  'use strict';

  function toggleAccordion(accId) {
    try { console.log('[sidebarAccordionFix] toggleAccordion:', accId); } catch(e) {}

    // 1) Accordion markup (recommended)
    var item = document.getElementById(accId) || document.querySelector('.nav-accordion-item#' + CSS.escape(accId));
    try { console.log('[sideba rAccordionFix] item found?', !!item, 'accId=', accId); } catch(e) {}

    if (item) {
      item.classList.toggle('open');
      var body = item.querySelector('.nav-accordion-body');
      if (body) {
        // Ensure clickable: override inline display
        var isOpen = item.classList.contains('open');
        body.style.display = isOpen ? 'block' : 'none';
        var innerLis = body.querySelectorAll('li');
        innerLis.forEach(function (li) {
          li.style.display = isOpen ? '' : 'none';
        });
      }
      return true;
    }

    // 2) Fallback: try toggling nested submenu container
    var any = document.querySelector('[onclick="toggleAccordion(\'' + accId + '\')"], [onclick="toggleAccordion(\"' + accId + '\")"]');
    if (!any) return false;

    var parent = any.closest('li');
    if (parent) {
      var target = parent.querySelector('.nav-accordion-body') || parent.querySelector('.sub-menu') || parent.querySelector('ul');
      if (target) {
        var show = getComputedStyle(target).display === 'none';
        target.style.display = show ? 'block' : 'none';
        return true;
      }
    }

    return false;
  }

  window.toggleAccordion = toggleAccordion;
})();