#pragma once

#include <cstdint>

#ifdef CMDRESP_HOST_TEST
#include "host_axis.hpp"
#else
#include <ap_axi_sdata.h>
#include <hls_stream.h>
using AxisWord = ap_axiu<32, 0, 0, 0>;
#endif

void fir4(hls::stream<AxisWord>& in_stream, hls::stream<AxisWord>& out_stream,
              uint32_t& halted, uint32_t& error, uint32_t& error_tx_id);
