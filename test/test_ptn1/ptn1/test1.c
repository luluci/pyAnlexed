
#include <stdio.h>

unsigned char					u8_1;				// flag1
extern unsigned char			u8_2 = TRUE;		// フラグ2
extern volatile unsigned char	u8_3 = 0;			// フラグ3
int								u32_1;				// global int var1

// 構造体A
struct tag_A {
	WORD	A;	} A_obj;	// Aオブジェクト


// 構造体B
//
typedef struct
{
	unsigned char B_mem_1;	// Bメンバ1
	unsigned B_mem_2;		// Bメンバ2
} B_obj;					// Bオブジェクト



// 構造体X
typedef struct tag_X
{
	WORD	mem1;		// mem1
	DWORD	mem2;		// member2
	LONG    mem3;       // メンバ3

	struct {
		BYTE mem4_1;	// member4-1
	} mem4;				// member4
	struct {
		BYTE mem5_1		:4;		// member5-1
		BYTE mem5_2		:2;		// member5-2
		BYTE mem5_3		:1;		// member5-3
		BYTE mem5_4		:1;		// member5-4
	} mem5;				// member5
} X;

// 構造体Y
typedef union {
	uint8_t mem1;	// mem1
	struct {
		uint8_t b1		:1; // bf1
		uint8_t b2		:1; // bf2
		uint8_t b3		:6; // bf3
	} mem1_bf;
} Y;


struct tag_Z
{
	WORD mem1;	// mem1
	DWORD mem2; // member2
	LONG mem3;	// メンバ3

	union
	{
		BYTE mem4_1;	// member4-1
		BYTE mem4_2;	// member4-2
	} mem4;				// member4

	WORD mem5;			// member5
} Z;	// 変数Z

int u32_2;		// global int var2

int main(void) {
	int local_x = 0;		// local x
	int local_y;			// local y

	return 0;
}
