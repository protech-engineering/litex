#include <hw/timer.h>
#include <hw/id.h>

#include "timer.h"

unsigned int get_system_frequency(void)
{
	return (CSR_ID_FREQ3 << 24)
		|(CSR_ID_FREQ2 << 16)
		|(CSR_ID_FREQ1 << 8)
		|CSR_ID_FREQ0;
}

void timer_enable(int en)
{
	CSR_TIMER0_EN = en;
}

unsigned int timer_get(void)
{
	return (CSR_TIMER0_COUNT3 << 24)
		|(CSR_TIMER0_COUNT2 << 16)
		|(CSR_TIMER0_COUNT1 << 8)
		|CSR_TIMER0_COUNT0;
}

void timer_set_counter(unsigned int value)
{
	CSR_TIMER0_COUNT3 = (value & 0xff000000) >> 24;
	CSR_TIMER0_COUNT2 = (value & 0x00ff0000) >> 16;
	CSR_TIMER0_COUNT1 = (value & 0x0000ff00) >> 8;
	CSR_TIMER0_COUNT0 = value & 0x000000ff;
}

void timer_set_reload(unsigned int value)
{
	CSR_TIMER0_RELOAD3 = (value & 0xff000000) >> 24;
	CSR_TIMER0_RELOAD2 = (value & 0x00ff0000) >> 16;
	CSR_TIMER0_RELOAD1 = (value & 0x0000ff00) >> 8;
	CSR_TIMER0_RELOAD0 = value & 0x000000ff;
}

void busy_wait(unsigned int ds)
{
	timer_enable(0);
	timer_set_reload(0);
	timer_set_counter(get_system_frequency()/10*ds);
	timer_enable(1);
	while(timer_get());
}
