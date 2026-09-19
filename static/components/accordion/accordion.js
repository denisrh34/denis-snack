/**
 * Accordion Component Behavior
 * Handles smooth height animations, keyboard navigation, multiple open support
 */

class AccordionComponent {
  constructor(accordionElement) {
    this.accordion = accordionElement;
    this.items = accordionElement.querySelectorAll('.accordion-item');
    this.allowMultiple = accordionElement.hasAttribute('data-multiple');
    this.triggers = [];
    this.contents = [];
    this.init();
  }

  init() {
    this.items.forEach((item, index) => {
      const trigger = item.querySelector('.accordion-trigger');
      const content = item.querySelector('.accordion-content');

      if (trigger && content) {
        this.triggers.push(trigger);
        this.contents.push(content);

        trigger.addEventListener('click', () => this.toggle(index));
        trigger.addEventListener('keydown', (e) => this.handleKeydown(e, index));

        // Set initial state
        const isOpen = trigger.getAttribute('aria-expanded') === 'true';
        if (isOpen) {
          this.openItem(index, false);
        }
      }
    });

    // Handle resize
    window.addEventListener('resize', () => this.updateOpenHeights());
  }

  handleKeydown(e, index) {
    const total = this.triggers.length;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.triggers[(index + 1) % total].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.triggers[(index - 1 + total) % total].focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      this.triggers[0].focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      this.triggers[total - 1].focus();
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this.toggle(index);
    }
  }

  toggle(index) {
    const trigger = this.triggers[index];
    const isOpen = trigger.getAttribute('aria-expanded') === 'true';

    if (isOpen) {
      this.close(index);
    } else {
      this.open(index);
    }
  }

  open(index, animate = true) {
    if (!this.allowMultiple) {
      this.closeAll(index);
    }

    const trigger = this.triggers[index];
    const content = this.contents[index];

    trigger.setAttribute('aria-expanded', 'true');
    content.hidden = false;

    if (animate) {
      this.animateHeight(content, 'open');
    } else {
      content.style.maxHeight = content.scrollHeight + 'px';
      content.style.paddingTop = '';
      content.style.paddingBottom = '';
    }
  }

  close(index, animate = true) {
    const trigger = this.triggers[index];
    const content = this.contents[index];

    trigger.setAttribute('aria-expanded', 'false');

    if (animate) {
      this.animateHeight(content, 'close');
    } else {
      content.hidden = true;
      content.style.maxHeight = '0';
      content.style.paddingTop = '0';
      content.style.paddingBottom = '0';
    }
  }

  closeAll(exceptIndex = -1) {
    this.triggers.forEach((trigger, i) => {
      if (i !== exceptIndex && trigger.getAttribute('aria-expanded') === 'true') {
        this.close(i);
      }
    });
  }

  animateHeight(content, direction) {
    if (direction === 'open') {
      content.hidden = false;
      content.style.maxHeight = '0';
      content.style.paddingTop = '0';
      content.style.paddingBottom = '0';

      // Force reflow
      content.offsetHeight;

      const targetHeight = content.scrollHeight;
      content.style.maxHeight = targetHeight + 'px';
      content.style.paddingTop = '';
      content.style.paddingBottom = '';

      content.addEventListener('transitionend', () => {
        if (content.style.maxHeight !== '0px') {
          content.style.maxHeight = 'none';
        }
      }, { once: true });
    } else {
      content.style.maxHeight = content.scrollHeight + 'px';
      content.offsetHeight;
      content.style.maxHeight = '0';
      content.style.paddingTop = '0';
      content.style.paddingBottom = '0';

      content.addEventListener('transitionend', () => {
        if (content.style.maxHeight === '0px') {
          content.hidden = true;
          content.style.maxHeight = '';
          content.style.paddingTop = '';
          content.style.paddingBottom = '';
        }
      }, { once: true });
    }
  }

  updateOpenHeights() {
    this.contents.forEach((content, i) => {
      if (!content.hidden && content.style.maxHeight !== 'none') {
        content.style.maxHeight = content.scrollHeight + 'px';
      }
    });
  }

  static init(selector = '.accordion') {
    document.querySelectorAll(selector).forEach(el => new AccordionComponent(el));
  }
}

// Auto-init
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    AccordionComponent.init();
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = AccordionComponent;
}