/**
 * Tabs Component Behavior
 * Handles keyboard navigation, automatic indicator positioning
 */

class TabsComponent {
  constructor(tabsElement) {
    this.tabs = tabsElement;
    this.triggers = tabsElement.querySelectorAll('.tabs-trigger');
    this.panels = tabsElement.querySelectorAll('.tabs-panel');
    this.indicator = tabsElement.querySelector('.tabs-indicator');
    this.orientation = tabsElement.getAttribute('aria-orientation') || 'horizontal';
    this.bindEvents();
    this.updateIndicator();
  }

  bindEvents() {
    this.triggers.forEach((trigger, index) => {
      trigger.addEventListener('click', () => this.activate(index));
      trigger.addEventListener('keydown', (e) => this.handleKeydown(e, index));
    });
  }

  handleKeydown(e, index) {
    const total = this.triggers.length;
    let newIndex = index;

    if (this.orientation === 'horizontal') {
      if (e.key === 'ArrowRight') newIndex = (index + 1) % total;
      else if (e.key === 'ArrowLeft') newIndex = (index - 1 + total) % total;
      else if (e.key === 'Home') newIndex = 0;
      else if (e.key === 'End') newIndex = total - 1;
      else return;
    } else {
      if (e.key === 'ArrowDown') newIndex = (index + 1) % total;
      else if (e.key === 'ArrowUp') newIndex = (index - 1 + total) % total;
      else if (e.key === 'Home') newIndex = 0;
      else if (e.key === 'End') newIndex = total - 1;
      else return;
    }

    e.preventDefault();
    this.activate(newIndex);
    this.triggers[newIndex].focus();
  }

  activate(index) {
    this.triggers.forEach((trigger, i) => {
      const selected = i === index;
      trigger.setAttribute('aria-selected', selected);
      trigger.tabIndex = selected ? 0 : -1;
      if (selected) trigger.classList.add('tabs-trigger-active');
      else trigger.classList.remove('tabs-trigger-active');
    });

    this.panels.forEach((panel, i) => {
      const selected = i === index;
      if (selected) {
        panel.hidden = false;
        panel.classList.add('tabs-panel-active');
      } else {
        panel.hidden = true;
        panel.classList.remove('tabs-panel-active');
      }
    });

    this.updateIndicator();
  }

  updateIndicator() {
    if (!this.indicator) return;

    const activeTrigger = this.tabs.querySelector('.tabs-trigger[aria-selected="true"]');
    if (!activeTrigger) return;

    const listRect = this.tabs.querySelector('.tabs-list').getBoundingClientRect();
    const triggerRect = activeTrigger.getBoundingClientRect();

    if (this.orientation === 'vertical') {
      this.indicator.style.height = `${triggerRect.height}px`;
      this.indicator.style.width = '';
      this.indicator.style.top = `${triggerRect.top - listRect.top}px`;
      this.indicator.style.left = '';
      this.indicator.style.transform = 'none';
    } else {
      this.indicator.style.width = `${triggerRect.width}px`;
      this.indicator.style.height = '';
      this.indicator.style.left = `${triggerRect.left - listRect.left}px`;
      this.indicator.style.top = '';
      this.indicator.style.transform = 'none';
    }
  }

  static init(selector = '.tabs') {
    document.querySelectorAll(selector).forEach(el => new TabsComponent(el));
  }

  static activate(tabsId, index) {
    const tabs = document.getElementById(tabsId);
    if (tabs && tabs._component) tabs._component.activate(index);
  }
}

// Auto-init and attach
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tabs').forEach(el => {
      el._component = new TabsComponent(el);
    });

    // Reposition indicator on resize
    let resizeTimeout;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        document.querySelectorAll('.tabs').forEach(el => {
          if (el._component) el._component.updateIndicator();
        });
      }, 100);
    });
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = TabsComponent;
}