/* Rome II DEI reinforcement capacity only. Runtime patch only; no logs or observers.
 * Lua 5.1 C functions return zero Lua values. No CRT or battle-script callbacks.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef void* H;
#define W __attribute__((stdcall))
#define API(ret,name,args) typedef ret (W *T##name) args; extern T##name p##name
API(H,GetModuleHandleA,(const char*));
API(u32,GetModuleFileNameA,(H,char*,u32));
API(H,GetCurrentProcess,(void));
API(int,ReadProcessMemory,(H,const void*,void*,u32,u32*));
API(H,CreateFileA,(const char*,u32,u32,void*,u32,u32,H));
API(int,ReadFile,(H,void*,u32,u32*,void*));
API(int,CloseHandle,(H));
API(int,VirtualProtect,(void*,u32,u32,u32*));
API(int,FlushInstructionCache,(H,const void*,u32));
API(int,GetModuleHandleExA,(u32,const char*,H*));
API(int,BCryptOpenAlgorithmProvider,(H*,const u16*,const u16*,u32));
API(int,BCryptGetProperty,(H,const u16*,u8*,u32,u32*,u32));
API(int,BCryptCreateHash,(H,H*,u8*,u32,u8*,u32,u32));
API(int,BCryptHashData,(H,u8*,u32,u32));
API(int,BCryptFinishHash,(H,u8*,u32,u32));
API(int,BCryptDestroyHash,(H));
API(int,BCryptCloseAlgorithmProvider,(H,u32));


#ifndef RDP_HOST_FIXTURE
typedef char pointer_must_be_32bit[sizeof(void*)==4?1:-1];
#endif
#include "patch_bytes.h"
static u32 base;
static int patch_active;
int rrc_install(void* lua);

static int same(const u8* a,const u8* b,u32 n) {
    u32 i;for(i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;
}
static int read(u32 a,void* p,u32 n) {
    u32 got=0;
    return a && pReadProcessMemory(pGetCurrentProcess(),(const void*)a,p,n,&got) && got==n;
}

static __attribute__((noinline)) int engine_hash(H engine) {
    static const u8 expected[32]={
      0x07,0xcb,0x22,0x15,0xb8,0x05,0x91,0x22,0x4a,0x5f,0x88,0x89,0x96,0x33,0x44,0xd5,
      0x60,0x49,0x2f,0x09,0xc4,0xd2,0x26,0x96,0xc9,0x88,0xb9,0x57,0xca,0x49,0xb2,0xb7};
    static const u16 sha[]={83,72,65,50,53,54,0};
    static const u16 obj[]={79,98,106,101,99,116,76,101,110,103,116,104,0};
    char path[1024];u8 object[1024],block[1024],digest[32];
    H f=0,alg=0,hash=0;u32 n,size=0,got=0;int ok=0;
    n=pGetModuleFileNameA(engine,path,sizeof(path));if(!n || n>=sizeof(path))return 0;
    f=pCreateFileA(path,0x80000000,7,0,3,0x80,0);if(f==(H)-1)return 0;
    if(pBCryptOpenAlgorithmProvider(&alg,sha,0,0)<0)goto done;
    if(pBCryptGetProperty(alg,obj,(u8*)&size,4,&got,0)<0 || size>sizeof(object) || !size)goto done;
    if(pBCryptCreateHash(alg,&hash,object,size,0,0,0)<0)goto done;
    for(;;) {
        if(!pReadFile(f,block,sizeof(block),&n,0))goto done;
        if(!n)break;
        if(pBCryptHashData(hash,block,n,0)<0)goto done;
    }
    if(pBCryptFinishHash(hash,digest,32,0)<0)goto done;
    ok=same(digest,expected,32);
done:
    if(hash)pBCryptDestroyHash(hash);
    if(alg)pBCryptCloseAlgorithmProvider(alg,0);
    pCloseHandle(f);return ok;
}
/* Pin this release to the tested engine and exact arrival-loop context. */
static int validate(H engine) {
    static const u8 arrival_sig[]={0x8b,0xcb,0xe8,0x49,0xdf,0x00,0x00,0x84,0xc0,0x0f,0x85,0x47,0x02,0x00,0x00};
    static const u8 batch_sig[]={0x83,0xfe,0x05,0x0f,0x82,0xaa,0xfd,0xff,0xff};
    u8 data[16];
    if(!engine_hash(engine))return 0;
    if(!read(base+0x2f65d0,data,15)||!same(data,arrival_sig,15))return 0;
    if(!read(base+0x2f681d,data,9)||!same(data,batch_sig,9))return 0;
    return 1;
}
static int match_at(u32 address,const u8* expected,u32 size) {
    u8 actual[16];return size<=sizeof(actual) && read(address,actual,size) && same(actual,expected,size);
}
static void copy_to(u32 address,const u8* data,u32 size) {
    volatile u8* target=(volatile u8*)address;u32 i;for(i=0;i<size;i++)target[i]=data[i];
}
/* One guarded five-byte callsite. Used by campaign and frontend state transitions.
 * Roll back on cache/read/protection
 * failure. Return -1 if rollback or original permissions cannot be confirmed.
 */
static int change_reinforcement_site(int enable) {
    u32 address=base+REINFORCEMENT_CHECK_RVA,old=0,ignored=0;
    const u8* after=enable?uncapped_reinforcement_check:original_reinforcement_check;
    const u8* before=enable?original_reinforcement_check:uncapped_reinforcement_check;
    int flushed,protected_ok;
    if(!match_at(address,before,5))return 0;
    if(!pVirtualProtect((void*)address,5,0x40,&old))return 0;
    copy_to(address,after,5);
    flushed=pFlushInstructionCache(pGetCurrentProcess(),(void*)address,5);
    if(flushed && match_at(address,after,5)) {
        if(pVirtualProtect((void*)address,5,old,&ignored))return 1;
    }
    copy_to(address,before,5);
    flushed=pFlushInstructionCache(pGetCurrentProcess(),(void*)address,5);
    protected_ok=pVirtualProtect((void*)address,5,old,&ignored);
    if(!flushed || !protected_ok || !match_at(address,before,5))return -1;
    return 0;
}
/* No disk writes: the engine DLL is opened only for SHA256 reading. */
static int install_patch(void) {
    H engine=pGetModuleHandleA("empire.retail.dll"),pinned=0;
    if(patch_active)return 1;
    base=(u32)engine;
    if(!engine || !validate(engine))return 0;
    if(!match_at(base+REINFORCEMENT_CHECK_RVA,original_reinforcement_check,5))return 0;
    if(!pGetModuleHandleExA(5,(const char*)rrc_install,&pinned))return 0;
    if(change_reinforcement_site(1)!=1)return 0;
    patch_active=1;return 1;
}
static int disable_patch(void) {
    if(!patch_active)return 1;
    if(change_reinforcement_site(0)!=1)return 0;
    patch_active=0;return 1;
}
int rrc_install(void* lua) {(void)lua;install_patch();return 0;}
int rrc_disable(void* lua) {(void)lua;disable_patch();return 0;}
int W DllMain(H module,u32 reason,void* reserved) {
    (void)module;(void)reason;(void)reserved;return 1;
}
