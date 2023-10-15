#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <generated/csr.h>

static inline unsigned int irq_getie(void) {

	unsigned int tmp;
	asm volatile ("csrr %0, mstatus" : "=r"(tmp) : );

  if (tmp & (1<<3)) { /* check mstatus.mie */
    return 1;
  }
  else {
    return 0;
  }
}

static inline void irq_setie(unsigned int ie) {

	if (ie) {
    asm volatile ("csrrs zero, mstatus, 1<<3"); /* atomic set mstatus.mie */
    }
  else {
    asm volatile ("csrrc zero, mstatus, 1<<3"); /* atomic clear mstatus.mie */
  }
}

static inline unsigned int irq_getmask(void) {
	return cpu_interrupt_enable_read();
}

static inline void irq_setmask(unsigned int mask) {
  cpu_interrupt_enable_write(mask);
}

static inline unsigned int irq_pending(void) {
  return cpu_interrupt_pending_read();
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
