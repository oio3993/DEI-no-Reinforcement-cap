/* Only the reinforcement arrival capacity call is replaced. */
#define REINFORCEMENT_CHECK_RVA 0x2f65d2u
/* The arrival loop calls the "at capacity" predicate and blocks if AL != 0.
 * Replace only this call with AL=0. Other arrival conditions and batch size stay.
 */
static const u8 original_reinforcement_check[5]={0xe8,0x49,0xdf,0x00,0x00};
static const u8 uncapped_reinforcement_check[5]={0x30,0xc0,0x90,0x90,0x90};
