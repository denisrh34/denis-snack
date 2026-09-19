/**
 * Modal Component Behavior
 * Handles focus trapping, ESC key, backdrop click, scroll lock
 */

class ModalComponent {
  constructor(overlayElement) {
    this.overlay = overlayElement;
    this.content = overlayElement.querySelector('.modal-content');
    this.closeBtn = overlayElement.querySelector('.modal-close');
    this.previousActiveElement = null;
    this.focusableElements = [];
    this.bindEvents();
  }

  bindEvents() {
    // Close button
    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => this.hide());
    }

    // Backdrop click
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.overlay) this.hide();
    });

    // ESC key
    this.keydownHandler = (e) => {
      if (e.key === 'Escape') this.hide();
      if (e.key === 'Tab') this.trapFocus(e);
    };
  }

  show() {
    this.previousActiveElement = document.activeElement;
    this.overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', this.keydownHandler);

    // Focus first focusable element
    setTimeout(() => this.focusFirstElement(), 0);
  }

  hide() {
    this.overlay.hidden = true;
    document.body.style.overflow = '';
    document.removeEventListener('keydown', this.keydownHandler);

    // Restore focus
    if (this.previousActiveElement) {
      this.previousActiveElement.focus();
    }
  }

  trapFocus(e) {
    this.updateFocusableElements();
    if (this.focusableElements.length === 0) return;

    const first = this.focusableElements[0];
    const last = this.focusableElements[this.focusableElements.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  updateFocusableElements() {
    const selectors = [
      'button:not([disabled])',
      '[href]',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ];
    this.focusableElements = Array.from(
      this.content.querySelectorAll(selectors.join(','))
    ).filter(el => el.offsetParent !== null);
  }

  focusFirstElement() {
    this.updateFocusableElements();
    if (this.focusableElements.length > 0) {
      this.focusableElements[0].focus();
    }
  }

  static init(selector = '.modal-overlay') {
    document.querySelectorAll(selector).forEach(el => new ModalComponent(el));
  }

  static open(modalId) {
    const modal = document.getElementById(modalId);
    if (modal && modal._component) modal._component.show();
  }

  static close(modalId) {
    const modal = document.getElementById(modalId);
    if (modal && modal._component) modal._component.hide();
  }
}

// Auto-init and attach to DOM elements
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.modal-overlay').forEach(el => {
      el._component = new ModalComponent(el);
    });
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = ModalComponent;
}